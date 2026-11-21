// SKYBOUND - flight-dynamics backend interface.
//
// The game module talks only to this interface. The concrete implementation
// (JSBSim, loaded dynamically) lives in this plugin. Keeping the seam here means:
//   * gameplay code has no LGPL dependency,
//   * the FDM can be replaced (or a deterministic test double substituted)
//     without touching aircraft or camera code,
//   * the licensing boundary is a single, auditable file.

#pragma once

#include "CoreMinimal.h"

/** Plain data mirror of the game-side state structs, expressed in SI units. */
struct FSKYFdmState
{
	double LatitudeDeg = 0.0;
	double LongitudeDeg = 0.0;
	double AltitudeM = 0.0;
	double PitchRad = 0.0;
	double RollRad = 0.0;
	double YawRad = 0.0;
	double TrueAirspeedMS = 0.0;
	double CalibratedAirspeedMS = 0.0;
	double GroundSpeedMS = 0.0;
	double VerticalSpeedMS = 0.0;
	double AngleOfAttackRad = 0.0;
	double SideSlipRad = 0.0;
	double Mach = 0.0;
	double FuelRemainingKg = 0.0;
	bool bWeightOnWheels = true;
	bool bStalled = false;
	double SimulationTimeS = 0.0;
};

struct FSKYFdmInputs
{
	double Elevator = 0.0;
	double Aileron = 0.0;
	double Rudder = 0.0;
	double Throttle = 0.0;
	double Flaps = 0.0;
	double Spoilers = 0.0;
	double PitchTrim = 0.0;
	bool bGearDown = true;
	bool bParkingBrake = true;
	bool bLeftBrake = false;
	bool bRightBrake = false;
	bool bReverseThrust = false;
};

class ISkyboundFdmBackend
{
public:
	virtual ~ISkyboundFdmBackend() = default;

	/** True when the native engine behind this backend is available. */
	virtual bool IsAvailable() const = 0;

	/** Human-readable reason the backend is unavailable, for the UI and logs. */
	virtual FString GetUnavailableReason() const = 0;

	/**
	 * Load an aircraft definition file and initialise the state.
	 * @param ModelPath      absolute path to the JSBSim aircraft XML
	 * @param LatDeg/LonDeg  WGS84 start position
	 * @param AltitudeM      altitude above the ellipsoid
	 * @param HeadingDeg     initial true heading
	 * @param bColdAndDark   start with engines off, systems unpowered
	 */
	virtual bool LoadModel(const FString& ModelPath, double LatDeg, double LonDeg,
	                       double AltitudeM, double HeadingDeg, bool bColdAndDark) = 0;

	virtual void UnloadModel() = 0;

	/** Advance the simulation by exactly FixedDeltaSeconds. */
	virtual bool Step(double FixedDeltaSeconds, const FSKYFdmInputs& Inputs) = 0;

	/** Read the current state. */
	virtual bool GetState(FSKYFdmState& OutState) const = 0;

	/** Backend name + version for the About screen and logs. */
	virtual FString GetBackendVersion() const = 0;
};

/**
 * Creates the production backend. Returns an object even when JSBSim is missing;
 * call IsAvailable() and surface GetUnavailableReason() to the user rather than
 * silently substituting a fake flight model (spec 26.2, 26.3).
 */
SKYBOUNDFLIGHTSIMULATION_API TUniquePtr<ISkyboundFdmBackend> CreateSkyboundFdmBackend();
