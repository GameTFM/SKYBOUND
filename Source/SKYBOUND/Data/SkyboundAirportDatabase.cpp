// SKYBOUND - airport database implementation.

#include "SkyboundAirportDatabase.h"

#include "SKYBOUND.h"
#include "Dom/JsonObject.h"
#include "HAL/FileManager.h"
#include "HAL/PlatformFileManager.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"
#include "Async/Async.h"

namespace
{
	/** Parsed on a worker thread, then handed to the game thread for adoption. */
	struct FIndexParseResult
	{
		bool bSuccess = false;
		FString Error;
		TArray<FSkyboundAirport> Airports;
		TArray<FString> SearchKeys;
	};

	/** Default location, overridable via [SkyboundAirportSubsystem] DataDirectory. */
	FString ResolveDataDirectory()
	{
		FString Configured;
		if (GConfig && GConfig->GetString(
				TEXT("SkyboundAirportSubsystem"), TEXT("DataDirectory"), Configured, GGameIni)
			&& !Configured.IsEmpty())
		{
			return Configured;
		}
		return FPaths::Combine(FPaths::ProjectContentDir(), TEXT("Data"), TEXT("Airports"));
	}

	/** Read a string field that may be null in the JSON. */
	FString ReadString(const TSharedPtr<FJsonObject>& Obj, const TCHAR* Field)
	{
		FString Value;
		if (Obj->TryGetStringField(Field, Value))
		{
			return Value;
		}
		return FString();
	}

	double ReadNumber(const TSharedPtr<FJsonObject>& Obj, const TCHAR* Field, bool& bOutPresent)
	{
		double Value = 0.0;
		bOutPresent = Obj->TryGetNumberField(Field, Value);
		return Value;
	}

	/**
	 * Parse airports_index.json into plain structs. Runs off the game thread.
	 * Field names must match Tools/AirportCatalogImporter/import_airports.py;
	 * Tests/run_all.py asserts that contract so a rename cannot slip through.
	 */
	bool ParseIndex(const FString& JsonText, FIndexParseResult& Out, FString& OutError)
	{
		TSharedPtr<FJsonObject> Root;
		const TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(JsonText);
		if (!FJsonSerializer::Deserialize(Reader, Root) || !Root.IsValid())
		{
			OutError = TEXT("airports_index.json is not valid JSON.");
			return false;
		}

		const TArray<TSharedPtr<FJsonValue>>* Records = nullptr;
		if (!Root->TryGetArrayField(TEXT("airports"), Records) || !Records)
		{
			OutError = TEXT("airports_index.json has no 'airports' array.");
			return false;
		}

		Out.Airports.Reserve(Records->Num());
		Out.SearchKeys.Reserve(Records->Num());

		for (const TSharedPtr<FJsonValue>& Entry : *Records)
		{
			const TSharedPtr<FJsonObject>* ObjPtr = nullptr;
			if (!Entry.IsValid() || !Entry->TryGetObject(ObjPtr) || !ObjPtr)
			{
				continue;
			}
			const TSharedPtr<FJsonObject>& Obj = *ObjPtr;

			FSkyboundAirport Airport;
			Airport.AirportId   = ReadString(Obj, TEXT("i"));
			Airport.Name        = ReadString(Obj, TEXT("n"));
			Airport.Type        = ReadString(Obj, TEXT("t"));
			Airport.Icao        = ReadString(Obj, TEXT("ic"));
			Airport.Iata        = ReadString(Obj, TEXT("ia"));
			Airport.CountryCode = ReadString(Obj, TEXT("c"));
			Airport.Municipality= ReadString(Obj, TEXT("m"));
			Airport.SceneryTier = ReadString(Obj, TEXT("tier"));
			Airport.DataCompleteness = ReadString(Obj, TEXT("dc"));

			bool bPresent = false;
			Airport.LatitudeDeg  = ReadNumber(Obj, TEXT("lat"), bPresent);
			Airport.LongitudeDeg = ReadNumber(Obj, TEXT("lon"), bPresent);
			Airport.ElevationFt  = ReadNumber(Obj, TEXT("el"), bPresent);
			Airport.bHasElevation = bPresent;

			double Scheduled = 0.0;
			Airport.bScheduledService = Obj->TryGetNumberField(TEXT("s"), Scheduled) && Scheduled != 0.0;

			double RunwayCount = 0.0;
			if (Obj->TryGetNumberField(TEXT("r"), RunwayCount))
			{
				Airport.RunwayCount = static_cast<int32>(RunwayCount);
			}

			if (Airport.AirportId.IsEmpty())
			{
				continue; // unusable record - skip rather than insert a ghost row
			}

			Out.Airports.Add(MoveTemp(Airport));

			// One pre-folded key: search then costs a single substring test.
			const FSkyboundAirport& Added = Out.Airports.Last();
			Out.SearchKeys.Add(
				FString::Printf(TEXT("%s %s %s %s"), *Added.Name, *Added.Icao,
				                *Added.Iata, *Added.Municipality).ToLower());
		}

		if (Out.Airports.Num() == 0)
		{
			OutError = TEXT("airports_index.json contained no usable airport records.");
			return false;
		}
		return true;
	}
}

void USkyboundAirportSubsystem::Initialize(FSubsystemCollectionBase& Collection)
{
	Super::Initialize(Collection);
	LoadIndexAsync();
}

void USkyboundAirportSubsystem::Deinitialize()
{
	Airports.Empty();
	SearchKeys.Empty();
	IndexById.Empty();
	RunwaysById.Empty();
	bReady = false;
	Super::Deinitialize();
}

void USkyboundAirportSubsystem::LoadIndexAsync()
{
	if (bLoadInFlight)
	{
		return;
	}

	const FString Path = FPaths::Combine(ResolveDataDirectory(), TEXT("airports_index.json"));
	if (!FPaths::FileExists(Path))
	{
		LoadError = FString::Printf(
			TEXT("Airport database not found: %s. Run Tools/AirportCatalogImporter/import_airports.py."),
			*Path);
		UE_LOG(LogSkyboundCatalog, Error, TEXT("%s"), *LoadError);
		return;
	}

	bLoadInFlight = true;

	// A weak pointer keeps the worker from touching a subsystem that has already
	// been torn down (game instance shutdown during a level transition).
	TWeakObjectPtr<USkyboundAirportSubsystem> WeakThis(this);
	const TSharedPtr<FIndexParseResult> Result = MakeShared<FIndexParseResult>();

	Async(EAsyncExecution::ThreadPool, [Path, Result]()
	{
		FString Json;
		if (!FFileHelper::LoadFileToString(Json, *Path))
		{
			Result->Error = FString::Printf(TEXT("Failed to read %s"), *Path);
			return;
		}
		FString Error;
		Result->bSuccess = ParseIndex(Json, *Result, Error);
		Result->Error = Error;
	})
	.Then([WeakThis, Result](auto)
	{
		AsyncTask(ENamedThreads::GameThread, [WeakThis, Result]()
		{
			if (USkyboundAirportSubsystem* Self = WeakThis.Get())
			{
				Self->OnIndexLoaded(Result->bSuccess, Result->Error);
				if (Result->bSuccess)
				{
					Self->Airports    = MoveTemp(Result->Airports);
					Self->SearchKeys  = MoveTemp(Result->SearchKeys);
					Self->IndexById.Empty(Self->Airports.Num());
					for (int32 i = 0; i < Self->Airports.Num(); ++i)
					{
						Self->IndexById.Add(Self->Airports[i].AirportId, i);
					}
				}
			}
		});
	});
}

void USkyboundAirportSubsystem::OnIndexLoaded(bool bSuccess, const FString& Error)
{
	bLoadInFlight = false;

	if (!bSuccess)
	{
		LoadError = Error;
		UE_LOG(LogSkyboundCatalog, Error, TEXT("Airport database load failed: %s"), *Error);
		return;
	}

	bReady = true;
	LoadError.Reset();

	UE_LOG(LogSkyboundCatalog, Log, TEXT("Airport database ready: %d sites"), Airports.Num());
	OnDatabaseReady.Broadcast();
}

TArray<int32> USkyboundAirportSubsystem::SearchAirports(const FSkyboundAirportSearchFilter& Filter,
                                                        int32 MaxResults) const
{
	TArray<int32> Results;
	if (!bReady || MaxResults <= 0)
	{
		return Results;
	}

	const FString Query = Filter.Query.TrimStartAndEnd();
	const FString Needle = Query.ToLower();
	const bool bHasQuery = !Needle.IsEmpty();

	// Exact identifier matches are what a pilot types, so they rank first rather
	// than appearing wherever alphabetical order happens to put them.
	if (bHasQuery)
	{
		for (int32 i = 0; i < Airports.Num() && Results.Num() < MaxResults; ++i)
		{
			const FSkyboundAirport& A = Airports[i];
			if (A.Icao.Equals(Query, ESearchCase::IgnoreCase) ||
			    A.Iata.Equals(Query, ESearchCase::IgnoreCase) ||
			    A.AirportId.Equals(Query, ESearchCase::IgnoreCase))
			{
				Results.Add(i);
			}
		}
	}

	for (int32 i = 0; i < Airports.Num() && Results.Num() < MaxResults; ++i)
	{
		const FSkyboundAirport& A = Airports[i];

		if (Filter.bExcludeClosed && A.Type.Equals(TEXT("closed"), ESearchCase::IgnoreCase))
		{
			continue;
		}
		if (Filter.bRequireRunway && A.RunwayCount <= 0)
		{
			continue;
		}
		if (Filter.bScheduledServiceOnly && !A.bScheduledService)
		{
			continue;
		}
		if (!Filter.CountryCode.IsEmpty() &&
		    !A.CountryCode.Equals(Filter.CountryCode, ESearchCase::IgnoreCase))
		{
			continue;
		}
		if (Filter.Types.Num() > 0)
		{
			bool bTypeMatches = false;
			for (const FString& Allowed : Filter.Types)
			{
				if (A.Type.Equals(Allowed, ESearchCase::IgnoreCase))
				{
					bTypeMatches = true;
					break;
				}
			}
			if (!bTypeMatches)
			{
				continue;
			}
		}

		if (bHasQuery && !SearchKeys[i].Contains(Needle))
		{
			continue;
		}

		// Avoid duplicating the exact matches collected above.
		if (!Results.Contains(i))
		{
			Results.Add(i);
		}
	}

	return Results;
}

bool USkyboundAirportSubsystem::GetAirport(int32 Index, FSkyboundAirport& OutAirport) const
{
	if (!Airports.IsValidIndex(Index))
	{
		return false;
	}
	OutAirport = Airports[Index];
	return true;
}

bool USkyboundAirportSubsystem::FindAirportById(const FString& AirportId,
                                               FSkyboundAirport& OutAirport) const
{
	if (const int32* Index = IndexById.Find(AirportId.ToLower()))
	{
		return GetAirport(*Index, OutAirport);
	}
	return false;
}

void USkyboundAirportSubsystem::LoadRunwaysIfNeeded()
{
	if (bRunwaysLoaded || bRunwaysLoading)
	{
		return;
	}
	bRunwaysLoading = true;

	const FString Path = FPaths::Combine(ResolveDataDirectory(), TEXT("airports_runways.json"));
	FString Json;
	if (!FFileHelper::LoadFileToString(Json, *Path))
	{
		LoadError = FString::Printf(TEXT("Runway data missing: %s"), *Path);
		UE_LOG(LogSkyboundCatalog, Warning, TEXT("%s"), *LoadError);
		bRunwaysLoading = false;
		return;
	}

	const double StartSeconds = FPlatformTime::Seconds();

	TSharedPtr<FJsonObject> Root;
	const TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(Json);
	if (!FJsonSerializer::Deserialize(Reader, Root) || !Root.IsValid())
	{
		LoadError = TEXT("airports_runways.json is not valid JSON.");
		UE_LOG(LogSkyboundCatalog, Error, TEXT("%s"), *LoadError);
		bRunwaysLoading = false;
		return;
	}

	const TSharedPtr<FJsonObject>* AirportsObj = nullptr;
	if (!Root->TryGetObjectField(TEXT("airports"), AirportsObj) || !AirportsObj)
	{
		LoadError = TEXT("airports_runways.json has no 'airports' object.");
		bRunwaysLoading = false;
		return;
	}

	RunwaysById.Reset();
	for (const TPair<FString, TSharedPtr<FJsonValue>>& Pair : (*AirportsObj)->Values)
	{
		const TSharedPtr<FJsonObject>* EntryObj = nullptr;
		if (!Pair.Value.IsValid() || !Pair.Value->TryGetObject(EntryObj) || !EntryObj)
		{
			continue;
		}
		const TArray<TSharedPtr<FJsonValue>>* RunwayArray = nullptr;
		if (!(*EntryObj)->TryGetArrayField(TEXT("runways"), RunwayArray) || !RunwayArray)
		{
			continue;
		}

		TArray<FSkyboundRunway>& Runways = RunwaysById.Add(Pair.Key);
		for (const TSharedPtr<FJsonValue>& RunwayValue : *RunwayArray)
		{
			const TSharedPtr<FJsonObject>* RunwayObj = nullptr;
			if (!RunwayValue.IsValid() || !RunwayValue->TryGetObject(RunwayObj) || !RunwayObj)
			{
				continue;
			}
			FSkyboundRunway Runway;
			Runway.Designation = ReadString(*RunwayObj, TEXT("designation"));
			Runway.Reciprocal  = ReadString(*RunwayObj, TEXT("reciprocal"));
			Runway.Surface     = ReadString(*RunwayObj, TEXT("surface"));

			double Value = 0.0;
			if ((*RunwayObj)->TryGetNumberField(TEXT("length_ft"), Value)) { Runway.LengthFt = Value; }
			if ((*RunwayObj)->TryGetNumberField(TEXT("width_ft"), Value))  { Runway.WidthFt = Value; }

			bool bFlag = false;
			if ((*RunwayObj)->TryGetBoolField(TEXT("lighted"), bFlag)) { Runway.bLighted = bFlag; }

			Runway.bHasHeading = (*RunwayObj)->TryGetNumberField(TEXT("heading_deg_true"), Value);
			if (Runway.bHasHeading)
			{
				Runway.HeadingDegTrue = Value;
			}
			Runways.Add(MoveTemp(Runway));
		}
	}

	bRunwaysLoaded = true;
	bRunwaysLoading = false;

	UE_LOG(LogSkyboundCatalog, Log,
		TEXT("Runway data loaded: %d airports in %.0f ms"),
		RunwaysById.Num(), (FPlatformTime::Seconds() - StartSeconds) * 1000.0);
}

bool USkyboundAirportSubsystem::GetRunways(const FString& AirportId,
                                          TArray<FSkyboundRunway>& OutRunways)
{
	LoadRunwaysIfNeeded();
	if (const TArray<FSkyboundRunway>* Found = RunwaysById.Find(AirportId.ToLower()))
	{
		OutRunways = *Found;
		return OutRunways.Num() > 0;
	}
	OutRunways.Reset();
	return false;
}
