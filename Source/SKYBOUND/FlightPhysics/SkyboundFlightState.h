// SKYBOUND - flight state exchanged between the FDM and the rendered aircraft.

#pragma once

#include "CoreMinimal.h"
#include "SkyboundFlightState.generated.h"

/**
 * One sampled state of the aircraft, in the units the simulation uses
 * internally (SI + radians). The aircraft actor converts to Unreal units at the
 * boundary; nothing else in the codebase sees mixed units.
 *
 * Geographic position is WGS84 geodetic: the Cesium georeference owns the
 * transform to Unreal world space, so the FDM never needs to know about
 * floating-point origin shifting.
 */
USTRUCT(BlueprintType)
struct FSkyboundFlightState
{
	GENERATED_BODY()

	/** WGS84 latitude, degrees. */
	UPROPERTY(BlueprintReadOnly, Category = "SKYBOUND|State")
	double LatitudeDeg = 0.0;

	/** WGS84 longitude, degrees. */
	UPROPERTY(BlueprintReadOnly, Category = "SKYBOUND|State")
	double LongitudeDeg = 0.0;

	/** Height above the WGS84 ellipsoid, metres. */
	UPROPERTY(BlueprintReadOnly, Category = "SKYBOUND|State")
	double AltitudeM = 0.0;

	/** Height above ground, metres (from the collision/terrain probe). */
	UPROPERTY(BlueprintReadOnly, Category = "SKYBOUND|State")
	double HeightAglM = 0.0;

	/** Body attitude, radians. */
	UPROPERTY(BlueprintReadOnly, Category = "SKYBOUND|State")
	double PitchRad = 0.0;

	UPROPERTY(BlueprintReadOnly, Category = "SKYBOUND|State")
	double RollRad = 0.0;

	UPROPERTY(BlueprintReadOnly, Category = "SKYBOUND|State")
	double YawRad = 0.0;

	/** True airspeed, m/s. */
	UPROPERTY(BlueprintReadOnly, Category = "SKYBOUND|State")
	double TrueAirspeedMS = 0.0;

	/** Calibrated airspeed, m/s. */
	UPROPERTY(BlueprintReadOnly, Category = "SKYBOUND|State")
	double CalibratedAirspeedMS = 0.0;

	/** Ground speed, m/s. */
	UPROPERTY(BlueprintReadOnly, Category = "SKYBOUND|State")
	double GroundSpeedMS = 0.0;

	/** Vertical speed, m/s (positive up). */
	UPROPERTY(BlueprintReadOnly, Category = "SKYBOUND|State")
	double VerticalSpeedMS = 0.0;

	UPROPERTY(BlueprintReadOnly, Category = "SKYBOUND|State")
	double AngleOfAttackRad = 0.0;

	UPROPERTY(BlueprintReadOnly, Category = "SKYBOUND|State")
	double SideSlipRad = 0.0;

	UPROPERTY(BlueprintReadOnly, Category = "SKYBOUND|State")
	double Mach = 0.0;

	/** True when any gear leg has weight on wheels. */
	UPROPERTY(BlueprintReadOnly, Category = "SKYBOUND|State")
	bool bWeightOnWheels = true;

	UPROPERTY(BlueprintReadOnly, Category = "SKYBOUND|State")
	bool bStalled = false;

	/** Simulation time of this sample, seconds. */
	UPROPERTY(BlueprintReadOnly, Category = "SKYBOUND|State")
	double SimulationTimeS = 0.0;

	/** Monotonic sample counter; used to detect stale/interpolated states. */
	UPROPERTY(BlueprintReadOnly, Category = "SKYBOUND|State")
	int64 SampleIndex = 0;
};

/**
 * Pilot (or autopilot) control inputs, normalised -1..1 where applicable.
 * Kept separate from the state so input handling, autopilot and replay all feed
 * the same interface.
 */
USTRUCT(BlueprintType)
struct FSkyboundControlInputs
{
	GENERATED_BODY()

	UPROPERTY(BlueprintReadWrite, Category = "SKYBOUND|Controls")
	double Elevator = 0.0;

	UPROPERTY(BlueprintReadWrite, Category = "SKYBOUND|Controls")
	double Aileron = 0.0;

	UPROPERTY(BlueprintReadWrite, Category = "SKYBOUND|Controls")
	double Rudder = 0.0;

	UPROPERTY(BlueprintReadWrite, Category = "SKYBOUND|Controls")
	double Throttle = 0.0;

	UPROPERTY(BlueprintReadWrite, Category = "SKYBOUND|Controls")
	double Flaps = 0.0;

	UPROPERTY(BlueprintReadWrite, Category = "SKYBOUND|Controls")
	double Spoilers = 0.0;

	UPROPERTY(BlueprintReadWrite, Category = "SKYBOUND|Controls")
	double PitchTrim = 0.0;

	UPROPERTY(BlueprintReadWrite, Category = "SKYBOUND|Controls")
	bool bGearDown = true;

	UPROPERTY(BlueprintReadWrite, Category = "SKYBOUND|Controls")
	bool bParkingBrake = true;

	UPROPERTY(BlueprintReadWrite, Category = "SKYBOUND|Controls")
	bool bLeftBrake = false;

	UPROPERTY(BlueprintReadWrite, Category = "SKYBOUND|Controls")
	bool bRightBrake = false;

	UPROPERTY(BlueprintReadWrite, Category = "SKYBOUND|Controls")
	bool bReverseThrust = false;
};
