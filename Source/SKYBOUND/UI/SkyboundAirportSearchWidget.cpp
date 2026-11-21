// SKYBOUND - airport search screen implementation.

#include "SkyboundAirportSearchWidget.h"

#include "SKYBOUND.h"
#include "Engine/GameInstance.h"

void USkyboundAirportSearchWidget::NativeConstruct()
{
	Super::NativeConstruct();

	UGameInstance* GameInstance = GetGameInstance();
	AirportSubsystem = GameInstance
		? GameInstance->GetSubsystem<USkyboundAirportSubsystem>()
		: nullptr;

	if (!AirportSubsystem)
	{
		UE_LOG(LogSkyboundCatalog, Error, TEXT("Airport search: no airport subsystem available."));
		OnDatabaseStateChanged(ESkyboundAirportListState::Failed,
			TEXT("Airport database unavailable in this game instance."));
		return;
	}

	if (AirportSubsystem->IsDatabaseReady())
	{
		HandleDatabaseReady();
	}
	else
	{
		// Subscribe first, then report the loading state: if the parse finished
		// between the two calls the delegate fires immediately and we still win.
		AirportSubsystem->OnDatabaseReady.AddUObject(this, &USkyboundAirportSearchWidget::HandleDatabaseReady);
		OnDatabaseStateChanged(ESkyboundAirportListState::Loading,
			TEXT("Loading airport database…"));
	}
}

void USkyboundAirportSearchWidget::NativeDestruct()
{
	if (AirportSubsystem)
	{
		AirportSubsystem->OnDatabaseReady.RemoveAll(this);
	}
	Super::NativeDestruct();
}

void USkyboundAirportSearchWidget::HandleDatabaseReady()
{
	OnDatabaseStateChanged(ESkyboundAirportListState::Ready, FString());
	ApplyFilters();
}

void USkyboundAirportSearchWidget::SetSearchQuery(const FString& Query)
{
	Filter.Query = Query;
	ApplyFilters();
}

void USkyboundAirportSearchWidget::SetTypeFilter(const FString& AirportType)
{
	Filter.Types.Reset();
	if (!AirportType.IsEmpty())
	{
		Filter.Types.Add(AirportType);
	}
	ApplyFilters();
}

void USkyboundAirportSearchWidget::SetCountryFilter(const FString& InCountryCode)
{
	Filter.CountryCode = InCountryCode;
	ApplyFilters();
}

void USkyboundAirportSearchWidget::SetScheduledServiceOnly(bool bOnlyScheduled)
{
	Filter.bScheduledServiceOnly = bOnlyScheduled;
	ApplyFilters();
}

void USkyboundAirportSearchWidget::SetRequireRunway(bool bRequire)
{
	Filter.bRequireRunway = bRequire;
	ApplyFilters();
}

void USkyboundAirportSearchWidget::RefreshResults()
{
	ApplyFilters();
}

void USkyboundAirportSearchWidget::ApplyFilters()
{
	ResultIndices.Reset();

	if (!AirportSubsystem || !AirportSubsystem->IsDatabaseReady())
	{
		OnResultsChanged();
		return;
	}

	ResultIndices = AirportSubsystem->SearchAirports(Filter, FMath::Max(1, MaxResults));
	CachedStatus.Reset();
	OnResultsChanged();
}

ESkyboundAirportListState USkyboundAirportSearchWidget::GetListState() const
{
	if (!AirportSubsystem)
	{
		return ESkyboundAirportListState::Failed;
	}
	if (AirportSubsystem->IsDatabaseReady())
	{
		return ESkyboundAirportListState::Ready;
	}
	return AirportSubsystem->GetLoadError().IsEmpty()
		? ESkyboundAirportListState::Loading
		: ESkyboundAirportListState::Failed;
}

FString USkyboundAirportSearchWidget::GetStatusMessage() const
{
	if (!AirportSubsystem)
	{
		return TEXT("Airport database unavailable.");
	}
	switch (GetListState())
	{
	case ESkyboundAirportListState::Loading:
		return TEXT("Loading airport database…");
	case ESkyboundAirportListState::Failed:
		return AirportSubsystem->GetLoadError();
	default:
		return FString::Printf(TEXT("%d of %d airports"), ResultIndices.Num(),
			AirportSubsystem->GetAirportCount());
	}
}

bool USkyboundAirportSearchWidget::GetResult(int32 ResultIndex, FSkyboundAirport& OutAirport) const
{
	if (!AirportSubsystem || !ResultIndices.IsValidIndex(ResultIndex))
	{
		return false;
	}
	return AirportSubsystem->GetAirport(ResultIndices[ResultIndex], OutAirport);
}

bool USkyboundAirportSearchWidget::GetResultRunways(int32 ResultIndex,
                                                    TArray<FSkyboundRunway>& OutRunways)
{
	FSkyboundAirport Airport;
	if (!GetResult(ResultIndex, Airport))
	{
		OutRunways.Reset();
		return false;
	}
	return AirportSubsystem->GetRunways(Airport.AirportId, OutRunways);
}

bool USkyboundAirportSearchWidget::SelectResult(int32 ResultIndex)
{
	FSkyboundAirport Airport;
	if (!GetResult(ResultIndex, Airport))
	{
		return false;
	}

	// Refuse a selection that cannot be flown from, rather than letting the user
	// pick an airport with no runway and land in an error later.
	if (!Airport.CanSpawnOnRunway())
	{
		UE_LOG(LogSkyboundCatalog, Warning,
			TEXT("Airport %s (%s) has no runway; selection rejected."),
			*Airport.AirportId, *Airport.Name);
		return false;
	}

	UE_LOG(LogSkyboundCatalog, Log, TEXT("Airport selected: %s (%s), %s, tier %s"),
		*Airport.Name, *Airport.Icao, *Airport.CountryCode, *Airport.SceneryTier);

	OnAirportChosen.Broadcast(Airport);
	return true;
}
