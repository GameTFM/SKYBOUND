// SKYBOUND - fixed-step flight model subsystem implementation.
//
// The accumulator pattern here is what makes handling frame-rate independent:
// physics advances in fixed 1/120 s steps regardless of how long the frame took,
// and renderers interpolate between the last two samples.

#include "SkyboundFlightModelSubsystem.h"

#include "SKYBOUND.h"
#include "SkyboundFdmBackend.h"
#include "Engine/GameInstance.h"
#include "Engine/World.h"
#include "Misc/Paths.h"

void USkyboundFlightModelSubsystem::Initialize(FSubsystemCollectionBase& Collection)
{
	Super::Initialize(Collection);

	Backend = CreateSkyboundFdmBackend();
	if (!Backend.IsValid())
	{
		ReportError(TEXT("No flight-dynamics backend could be created."));
		return;
	}

	if (!Backend->IsAvailable())
	{
		// Report, never substitute a fake flight model (spec 26.2).
		ReportError(Backend->GetUnavailableReason());
		return;
	}

	UE_LOG(LogSkyboundFdm, Log, TEXT("Flight dynamics backend: %s"),
		*Backend->GetBackendVersion());
}

void USkyboundFlightModelSubsystem::Deinitialize()
{
	if (Backend.IsValid())
	{
		Backend->UnloadModel();
		Backend.Reset();
	}
	bAircraftLoaded = false;
	Super::Deinitialize();
}

bool USkyboundFlightModelSubsystem::LoadAircraft(const FString& AircraftId,
	double LatitudeDeg, double LongitudeDeg, double AltitudeM,
	double InitialHeadingDeg, bool bColdAndDark)
{
	if (!Backend.IsValid() || !Backend->IsAvailable())
	{
		ReportError(TEXT("Cannot load an aircraft: flight dynamics are unavailable."));
		return false;
	}

	// Definitions live outside the pak so they can be inspected and updated
	// without re-cooking (see DefaultGame.ini staging rules).
	const FString ModelName = FString::Printf(TEXT("skybound_%s"),
		*AircraftId.Replace(TCHAR('-'), TCHAR('_')));
	const FString ModelPath = FPaths::Combine(FPaths::ProjectContentDir(), TEXT("Data"),
		TEXT("FlightModels"), ModelName, ModelName + TEXT(".xml"));

	if (!FPaths::FileExists(ModelPath))
	{
		ReportError(FString::Printf(
			TEXT("Aircraft definition not found: %s. Run Tools/FlightDynamics/export_jsbsim.py."),
			*ModelPath));
		return false;
	}

	if (!Backend->LoadModel(ModelPath, LatitudeDeg, LongitudeDeg, AltitudeM,
	                       InitialHeadingDeg, bColdAndDark))
	{
		ReportError(Backend->GetUnavailableReason());
		return false;
	}

	AccumulatorS = 0.0;
	bAircraftLoaded = true;
	bPaused = false;
	PreviousState = FSkyboundFlightState();
	CurrentState = FSkyboundFlightState();
	CurrentState.LatitudeDeg = LatitudeDeg;
	CurrentState.LongitudeDeg = LongitudeDeg;
	CurrentState.AltitudeM = AltitudeM;
	CurrentState.YawRad = FMath::DegreesToRadians(InitialHeadingDeg);

	UE_LOG(LogSkyboundFdm, Log, TEXT("Loaded aircraft '%s' at %.5f, %.5f (%.0f m)"),
		*AircraftId, LatitudeDeg, LongitudeDeg, AltitudeM);
	return true;
}

void USkyboundFlightModelSubsystem::UnloadAircraft()
{
	if (Backend.IsValid())
	{
		Backend->UnloadModel();
	}
	bAircraftLoaded = false;
}

void USkyboundFlightModelSubsystem::SetSimulationRate(ESkyboundSimulationRate Rate)
{
	switch (Rate)
	{
	case ESkyboundSimulationRate::High:   FixedStepS = 1.0 / 120.0; break;
	case ESkyboundSimulationRate::Medium: FixedStepS = 1.0 / 60.0;  break;
	case ESkyboundSimulationRate::Low:    FixedStepS = 1.0 / 30.0;  break;
	}
	AccumulatorS = 0.0;
}

void USkyboundFlightModelSubsystem::SetPaused(bool bInPaused)
{
	bPaused = bInPaused;
}

void USkyboundFlightModelSubsystem::SetControlInputs(const FSkyboundControlInputs& Inputs)
{
	// Held rather than applied immediately: inputs are sampled by the fixed-step
	// loop so a fast frame cannot apply the same stick position twice.
	PendingInputs = Inputs;
}

void USkyboundFlightModelSubsystem::Tick(float DeltaTime)
{
	if (!bAircraftLoaded || bPaused || !Backend.IsValid())
	{
		return;
	}

	// Clamp the frame contribution so a long hitch (shader compile, level
	// stream) cannot trigger hundreds of catch-up physics steps.
	AccumulatorS += FMath::Min(static_cast<double>(DeltaTime), MaxStepsPerFrame * FixedStepS);

	int32 Steps = 0;
	while (AccumulatorS >= FixedStepS && Steps < MaxStepsPerFrame)
	{
		StepFixed(FixedStepS);
		AccumulatorS -= FixedStepS;
		++Steps;
	}
}

void USkyboundFlightModelSubsystem::StepFixed(double FixedDeltaSeconds)
{
	FSKYFdmInputs Inputs;
	Inputs.Elevator      = PendingInputs.Elevator;
	Inputs.Aileron       = PendingInputs.Aileron;
	Inputs.Rudder        = PendingInputs.Rudder;
	Inputs.Throttle      = PendingInputs.Throttle;
	Inputs.Flaps         = PendingInputs.Flaps;
	Inputs.Spoilers      = PendingInputs.Spoilers;
	Inputs.PitchTrim     = PendingInputs.PitchTrim;
	Inputs.bGearDown     = PendingInputs.bGearDown;
	Inputs.bParkingBrake = PendingInputs.bParkingBrake;
	Inputs.bLeftBrake    = PendingInputs.bLeftBrake;
	Inputs.bRightBrake   = PendingInputs.bRightBrake;
	Inputs.bReverseThrust = PendingInputs.bReverseThrust;

	if (!Backend->Step(FixedDeltaSeconds, Inputs))
	{
		ReportError(TEXT("Flight dynamics step failed; simulation paused."));
		bPaused = true;
		return;
	}

	PreviousState = CurrentState;
	FSKYFdmState Raw;
	if (Backend->GetState(Raw))
	{
		CurrentState.LatitudeDeg           = Raw.LatitudeDeg;
		CurrentState.LongitudeDeg          = Raw.LongitudeDeg;
		CurrentState.AltitudeM             = Raw.AltitudeM;
		CurrentState.PitchRad              = Raw.PitchRad;
		CurrentState.RollRad               = Raw.RollRad;
		CurrentState.YawRad                = Raw.YawRad;
		CurrentState.TrueAirspeedMS        = Raw.TrueAirspeedMS;
		CurrentState.CalibratedAirspeedMS  = Raw.CalibratedAirspeedMS;
		CurrentState.GroundSpeedMS         = Raw.GroundSpeedMS;
		CurrentState.VerticalSpeedMS       = Raw.VerticalSpeedMS;
		CurrentState.AngleOfAttackRad      = Raw.AngleOfAttackRad;
		CurrentState.SideSlipRad           = Raw.SideSlipRad;
		CurrentState.Mach                  = Raw.Mach;
		CurrentState.bWeightOnWheels       = Raw.bWeightOnWheels;
		CurrentState.bStalled              = Raw.bStalled;
		CurrentState.SimulationTimeS       = Raw.SimulationTimeS;
		++CurrentState.SampleIndex;
	}

	PublishState();
}

void USkyboundFlightModelSubsystem::PublishState()
{
	OnFlightStateUpdated.Broadcast(CurrentState, PreviousState);
}

FSkyboundFlightState USkyboundFlightModelSubsystem::GetInterpolatedState(float Alpha) const
{
	// Linear interpolation is adequate at 120 Hz; attitude wrapping is handled by
	// shortest-arc interpolation so a heading crossing 0/360 does not spin.
	FSkyboundFlightState Out = CurrentState;
	const float A = FMath::Clamp(Alpha, 0.0f, 1.0f);
	auto Lerp = [A](double From, double To) { return From + (To - From) * A; };
	auto LerpAngle = [A](double From, double To)
	{
		double Delta = FMath::FindDeltaAngleRadians(From, To);
		return From + Delta * A;
	};

	Out.LatitudeDeg     = Lerp(PreviousState.LatitudeDeg, CurrentState.LatitudeDeg);
	Out.LongitudeDeg    = Lerp(PreviousState.LongitudeDeg, CurrentState.LongitudeDeg);
	Out.AltitudeM       = Lerp(PreviousState.AltitudeM, CurrentState.AltitudeM);
	Out.PitchRad        = LerpAngle(PreviousState.PitchRad, CurrentState.PitchRad);
	Out.RollRad         = LerpAngle(PreviousState.RollRad, CurrentState.RollRad);
	Out.YawRad          = LerpAngle(PreviousState.YawRad, CurrentState.YawRad);
	Out.TrueAirspeedMS  = Lerp(PreviousState.TrueAirspeedMS, CurrentState.TrueAirspeedMS);
	return Out;
}

double USkyboundFlightModelSubsystem::GetFuelRemainingKg() const
{
	return 0.0; // populated when the backend exposes fuel state (DL-005)
}

void USkyboundFlightModelSubsystem::ReportError(const FString& Message)
{
	LastError = Message;
	UE_LOG(LogSkyboundFdm, Error, TEXT("%s"), *Message);
	OnFdmError.Broadcast(Message);
}

bool USkyboundFlightModelSubsystem::IsTickable() const
{
	return bAircraftLoaded && !bPaused;
}

UWorld* USkyboundFlightModelSubsystem::GetTickableGameObjectWorld() const
{
	const UGameInstance* GameInstance = GetGameInstance();
	return GameInstance ? GameInstance->GetWorld() : nullptr;
}

TStatId USkyboundFlightModelSubsystem::GetStatId() const
{
	RETURN_QUICK_DECLARE_CYCLE_STAT(USkyboundFlightModelSubsystem, STATGROUP_Tickables);
}
