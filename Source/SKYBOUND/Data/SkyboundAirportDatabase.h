// SKYBOUND - airport database.
//
// Loads Content/Data/Airports/airports_index.json (86k sites, ~15 MB) at startup
// and Content/Data/Airports/airports_runways.json (~23 MB) on first use, so the
// airport search screen can answer immediately without parsing the runway file.
//
// The JSON uses compact keys (i, n, t, lat, lon, ...) because 86,377 records
// times full field names is tens of megabytes of pure key text. The mapping is
// declared once, in FSkyboundAirportDatabase::ParseIndex, and asserted against
// the Python importer by Tests/run_all.py so the two cannot drift apart silently.

#pragma once

#include "CoreMinimal.h"
#include "Subsystems/GameInstanceSubsystem.h"
#include "SkyboundAirportDatabase.generated.h"

/** One runway end-pair as imported from the public-domain OurAirports dataset. */
USTRUCT(BlueprintType)
struct FSkyboundRunway
{
	GENERATED_BODY()

	/** Threshold identifier, e.g. "27L". */
	UPROPERTY(BlueprintReadOnly, Category = "SKYBOUND|Airport")
	FString Designation;

	/** Reciprocal end, e.g. "09R". */
	UPROPERTY(BlueprintReadOnly, Category = "SKYBOUND|Airport")
	FString Reciprocal;

	UPROPERTY(BlueprintReadOnly, Category = "SKYBOUND|Airport")
	double LengthFt = 0.0;

	UPROPERTY(BlueprintReadOnly, Category = "SKYBOUND|Airport")
	double WidthFt = 0.0;

	/** asphalt, concrete, grass, water, ... */
	UPROPERTY(BlueprintReadOnly, Category = "SKYBOUND|Airport")
	FString Surface;

	UPROPERTY(BlueprintReadOnly, Category = "SKYBOUND|Airport")
	bool bLighted = false;

	/** True heading of this end, degrees [0,360). Used to spawn aligned. */
	UPROPERTY(BlueprintReadOnly, Category = "SKYBOUND|Airport")
	double HeadingDegTrue = 0.0;

	UPROPERTY(BlueprintReadOnly, Category = "SKYBOUND|Airport")
	bool bHasHeading = false;
};

/** One airport/site. Enough to search, place and spawn. */
USTRUCT(BlueprintType)
struct FSkyboundAirport
{
	GENERATED_BODY()

	UPROPERTY(BlueprintReadOnly, Category = "SKYBOUND|Airport")
	FString AirportId;

	UPROPERTY(BlueprintReadOnly, Category = "SKYBOUND|Airport")
	FString Name;

	/** large_airport, medium_airport, small_airport, heliport, seaplane_base, ... */
	UPROPERTY(BlueprintReadOnly, Category = "SKYBOUND|Airport")
	FString Type;

	UPROPERTY(BlueprintReadOnly, Category = "SKYBOUND|Airport")
	FString Icao;

	UPROPERTY(BlueprintReadOnly, Category = "SKYBOUND|Airport")
	FString Iata;

	UPROPERTY(BlueprintReadOnly, Category = "SKYBOUND|Airport")
	FString CountryCode;

	UPROPERTY(BlueprintReadOnly, Category = "SKYBOUND|Airport")
	FString Municipality;

	UPROPERTY(BlueprintReadOnly, Category = "SKYBOUND|Airport")
	double LatitudeDeg = 0.0;

	UPROPERTY(BlueprintReadOnly, Category = "SKYBOUND|Airport")
	double LongitudeDeg = 0.0;

	UPROPERTY(BlueprintReadOnly, Category = "SKYBOUND|Airport")
	double ElevationFt = 0.0;

	UPROPERTY(BlueprintReadOnly, Category = "SKYBOUND|Airport")
	bool bHasElevation = false;

	UPROPERTY(BlueprintReadOnly, Category = "SKYBOUND|Airport")
	bool bScheduledService = false;

	UPROPERTY(BlueprintReadOnly, Category = "SKYBOUND|Airport")
	int32 RunwayCount = 0;

	/** hero | generated | data_only - how detailed the scenery is (or is not). */
	UPROPERTY(BlueprintReadOnly, Category = "SKYBOUND|Airport")
	FString SceneryTier;

	/**
	 * complete | missing_runways | no_runways.
	 * 'missing_runways' means the upstream dataset lists the site (and may even
	 * say airlines serve it) but supplies no usable runway - a data gap, not a
	 * SKYBOUND bug. The UI explains it instead of showing an empty runway list.
	 */
	UPROPERTY(BlueprintReadOnly, Category = "SKYBOUND|Airport")
	FString DataCompleteness;

	/** False when the airport cannot be spawned at (no runway at all). */
	UFUNCTION(BlueprintPure, Category = "SKYBOUND|Airport")
	bool CanSpawnOnRunway() const { return RunwayCount > 0; }

	/** True when the site's main data is missing upstream, for UI messaging. */
	UFUNCTION(BlueprintPure, Category = "SKYBOUND|Airport")
	bool IsMissingRunwayData() const { return DataCompleteness == TEXT("missing_runways"); }
};

DECLARE_MULTICAST_DELEGATE(FOnSkyboundAirportDatabaseReady);

/** Filters applied to a search. Defaults match "show me everything". */
USTRUCT(BlueprintType)
struct FSkyboundAirportSearchFilter
{
	GENERATED_BODY()

	/** Free text: matches name, ICAO, IATA or municipality. */
	UPROPERTY(BlueprintReadWrite, Category = "SKYBOUND|Airport")
	FString Query;

	/** Restrict to these types; empty means all types. */
	UPROPERTY(BlueprintReadWrite, Category = "SKYBOUND|Airport")
	TArray<FString> Types;

	UPROPERTY(BlueprintReadWrite, Category = "SKYBOUND|Airport")
	FString CountryCode;

	UPROPERTY(BlueprintReadWrite, Category = "SKYBOUND|Airport")
	bool bScheduledServiceOnly = false;

	/** Hide sites with no runway - the usual choice for a quick-start list. */
	UPROPERTY(BlueprintReadWrite, Category = "SKYBOUND|Airport")
	bool bRequireRunway = true;

	/** Hide closed sites, which exist in the dataset but cannot be flown from. */
	UPROPERTY(BlueprintReadWrite, Category = "SKYBOUND|Airport")
	bool bExcludeClosed = true;
};

/**
 * Owns the airport database for the lifetime of the game instance.
 *
 * Startup behaviour: Initialize() kicks a background parse of the index and
 * broadcasts OnDatabaseReady when it is usable. The search screen binds to that
 * delegate and shows a loading state until it fires - it never blocks the game
 * thread on a 15 MB JSON parse.
 */
UCLASS()
class SKYBOUND_API USkyboundAirportSubsystem : public UGameInstanceSubsystem
{
	GENERATED_BODY()

public:
	virtual void Initialize(FSubsystemCollectionBase& Collection) override;
	virtual void Deinitialize() override;

	UFUNCTION(BlueprintPure, Category = "SKYBOUND|Airport")
	bool IsDatabaseReady() const { return bReady; }

	UFUNCTION(BlueprintPure, Category = "SKYBOUND|Airport")
	int32 GetAirportCount() const { return Airports.Num(); }

	/**
	 * Search the index. Returns at most MaxResults indices into the airport list.
	 * Case-insensitive; exact ICAO/IATA matches are ranked first.
	 */
	UFUNCTION(BlueprintCallable, Category = "SKYBOUND|Airport")
	TArray<int32> SearchAirports(const FSkyboundAirportSearchFilter& Filter, int32 MaxResults = 100) const;

	UFUNCTION(BlueprintPure, Category = "SKYBOUND|Airport")
	bool GetAirport(int32 Index, FSkyboundAirport& OutAirport) const;

	UFUNCTION(BlueprintPure, Category = "SKYBOUND|Airport")
	bool FindAirportById(const FString& AirportId, FSkyboundAirport& OutAirport) const;

	/** Runway detail. Loads the runway file on first call; true if available. */
	UFUNCTION(BlueprintCallable, Category = "SKYBOUND|Airport")
	bool GetRunways(const FString& AirportId, TArray<FSkyboundRunway>& OutRunways);

	/** Last load error, empty when healthy. Surfaced in the UI, never swallowed. */
	UFUNCTION(BlueprintPure, Category = "SKYBOUND|Airport")
	const FString& GetLoadError() const { return LoadError; }

	FOnSkyboundAirportDatabaseReady OnDatabaseReady;

private:
	void LoadIndexAsync();
	void OnIndexLoaded(bool bSuccess, const FString& Error);
	void LoadRunwaysIfNeeded();

	TArray<FSkyboundAirport> Airports;

	/**
	 * Lower-cased "name icao iata municipality" per airport, parallel to
	 * Airports. Built once at load so a search is one substring test per record
	 * instead of four case-folded comparisons allocating a string each time.
	 */
	TArray<FString> SearchKeys;
	TMap<FString, int32> IndexById;

	/** Runway data, keyed by airport id. Loaded lazily on first request. */
	TMap<FString, TArray<FSkyboundRunway>> RunwaysById;
	bool bRunwaysLoaded = false;
	bool bRunwaysLoading = false;

	bool bReady = false;
	bool bLoadInFlight = false;
	FString LoadError;
};
