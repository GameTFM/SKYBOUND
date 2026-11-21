// SKYBOUND - flight model subsystem.
//
// Owns the fixed-timestep flight-dynamics loop. Physics rate is independent of
// frame rate (spec 3.3): the subsystem accumulates real time and steps the FDM
// at a fixed 120 Hz, publishing an interpolated state to renderers.
//
// The actual 6-DOF integration is performed by JSBSim inside the
// FlightSimulation plugin, reached through ISkyboundFdmBackend. This subsystem
// is deliberately backend-agnostic so the FDM can be swapped or mocked in tests
// without touching gameplay code.

#pragma once

#include "CoreMinimal.h"
#include "Subsystems/GameInstanceSubsystem.h"
#include "Tickable.h"
#include "SkyboundFlightState.h"
#include "SkyboundFlightModelSubsystem.generated.h"

class ISkyboundFdmBackend;

DECLARE_MULTICAST_DELEGATE_TwoParams(FOnSkyboundFlightStateUpdated,
                                     const FSkyboundFlightState& /*Current*/,
                                     const FSkyboundFlightState& /*Previous*/);

DECLARE_MULTICAST_DELEGATE_OneParam(FOnSkyboundFdmError, const FString& /*Message*/);

UENUM(BlueprintType)
enum class ESkyboundSimulationRate : uint8
{
	/** 120 Hz - default; matches JSBSim's usual integration rate. */
	High = 0,
	/** 60 Hz - reduced CPU cost on low-end machines. */
	Medium = 1,
	/** 30 Hz - deliberately coarse; for debugging only. */
	Low = 2
};

UCLASS()
class SKYBOUND_API USkyboundFlightModelSubsystem : public UGameInstanceSubsystem, public FTickableGameObject
{
	GENERATED_BODY()

public:
	// --- UGameInstanceSubsystem -------------------------------------------
	virtual void Initialize(FSubsystemCollectionBase& Collection) override;
	virtual void Deinitialize() override;

	// --- FTickableGameObject ----------------------------------------------
	virtual void Tick(float DeltaTime) override;
	virtual bool IsTickable() const override;
	virtual bool IsTickableWhenPaused() const override { return false; }
	virtual bool IsTickableInEditor() const override { return false; }
	virtual TStatId GetStatId() const override;
	virtual UWorld* GetTickableGameObjectWorld() const override;

	// --- Simulation control ------------------------------------------------
	/** Load an aircraft definition and place it at a geographic position. */
	UFUNCTION(BlueprintCallable, Category = "SKYBOUND|Flight")
	bool LoadAircraft(const FString& AircraftId, double LatitudeDeg, double LongitudeDeg,
	                  double AltitudeM, double InitialHeadingDeg, bool bColdAndDark);

	UFUNCTION(BlueprintCallable, Category = "SKYBOUND|Flight")
	void UnloadAircraft();

	UFUNCTION(BlueprintCallable, Category = "SKYBOUND|Flight")
	void SetSimulationRate(ESkyboundSimulationRate Rate);

	UFUNCTION(BlueprintCallable, Category = "SKYBOUND|Flight")
	void SetPaused(bool bPaused);

	UFUNCTION(BlueprintCallable, Category = "SKYBOUND|Flight")
	bool IsSimulationRunning() const { return bAircraftLoaded && !bPaused; }

	/** Feed pilot/autopilot inputs into the FDM. */
	UFUNCTION(BlueprintCallable, Category = "SKYBOUND|Flight")
	void SetControlInputs(const FSkyboundControlInputs& Inputs);

	/** Latest state, safe to read from any game thread tick. */
	UFUNCTION(BlueprintPure, Category = "SKYBOUND|Flight")
	const FSkyboundFlightState& GetCurrentState() const { return CurrentState; }

	/** Interpolated state for rendering between physics steps. */
	FSkyboundFlightState GetInterpolatedState(float Alpha) const;

	/** Fuel remaining, kg (0 when no aircraft is loaded). */
	UFUNCTION(BlueprintPure, Category = "SKYBOUND|Flight")
	double GetFuelRemainingKg() const;

	/** Last error reported by the FDM backend, empty if none. */
	UFUNCTION(BlueprintPure, Category = "SKYBOUND|Flight")
	const FString& GetLastError() const { return LastError; }

	FOnSkyboundFlightStateUpdated OnFlightStateUpdated;
	FOnSkyboundFdmError OnFdmError;

private:
	void StepFixed(double FixedDeltaSeconds);
	void PublishState();
	void ReportError(const FString& Message);

	TUniquePtr<ISkyboundFdmBackend> Backend;

	FSkyboundFlightState CurrentState;
	FSkyboundFlightState PreviousState;
	FSkyboundControlInputs PendingInputs;

	/** Physics accumulator, seconds. */
	double AccumulatorS = 0.0;
	double FixedStepS = 1.0 / 120.0;
	bool bAircraftLoaded = false;
	bool bPaused = false;
	FString LastError;

	/** Guards against a spiral of death if a single frame takes very long. */
	static constexpr int32 MaxStepsPerFrame = 8;
};
