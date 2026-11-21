// SKYBOUND - airport search screen.
//
// C++ base for the airport picker. It owns no visuals: a UMG widget derives from
// it and binds the Blueprint events. All search logic and database access lives
// here so the screen cannot drift from the data layer.
//
// The list is only populated once USkyboundAirportSubsystem reports ready, which
// happens after the startup parse of airports_index.json completes on a worker
// thread. Until then the screen shows a loading state - it never displays an
// empty list as if the dataset were empty.

#pragma once

#include "CoreMinimal.h"
#include "Blueprint/UserWidget.h"
#include "Data/SkyboundAirportDatabase.h"
#include "SkyboundAirportSearchWidget.generated.h"

DECLARE_DYNAMIC_MULTICAST_DELEGATE_OneParam(FOnSkyboundAirportChosen, const FSkyboundAirport&, Airport);

UENUM(BlueprintType)
enum class ESkyboundAirportListState : uint8
{
	/** Startup parse still running. */
	Loading,
	/** Database loaded and search is usable. */
	Ready,
	/** Load failed - Message explains why; the list stays empty on purpose. */
	Failed
};

UCLASS(Abstract, Blueprintable)
class SKYBOUND_API USkyboundAirportSearchWidget : public UUserWidget
{
	GENERATED_BODY()

public:
	virtual void NativeConstruct() override;
	virtual void NativeDestruct() override;

	// --- User-facing actions ------------------------------------------------

	/** Free text: name, ICAO, IATA or city. Applies immediately. */
	UFUNCTION(BlueprintCallable, Category = "SKYBOUND|Airport Search")
	void SetSearchQuery(const FString& Query);

	/** e.g. "large_airport". Empty clears the filter. */
	UFUNCTION(BlueprintCallable, Category = "SKYBOUND|Airport Search")
	void SetTypeFilter(const FString& AirportType);

	UFUNCTION(BlueprintCallable, Category = "SKYBOUND|Airport Search")
	void SetCountryFilter(const FString& InCountryCode);

	UFUNCTION(BlueprintCallable, Category = "SKYBOUND|Airport Search")
	void SetScheduledServiceOnly(bool bOnlyScheduled);

	/** Most useful default is true: only show airports you can actually spawn on. */
	UFUNCTION(BlueprintCallable, Category = "SKYBOUND|Airport Search")
	void SetRequireRunway(bool bRequire);

	/** Re-run the current query. Called automatically by every setter. */
	UFUNCTION(BlueprintCallable, Category = "SKYBOUND|Airport Search")
	void RefreshResults();

	// --- Results ------------------------------------------------------------

	UFUNCTION(BlueprintPure, Category = "SKYBOUND|Airport Search")
	ESkyboundAirportListState GetListState() const;

	UFUNCTION(BlueprintPure, Category = "SKYBOUND|Airport Search")
	FString GetStatusMessage() const;

	UFUNCTION(BlueprintPure, Category = "SKYBOUND|Airport Search")
	int32 GetResultCount() const { return ResultIndices.Num(); }

	UFUNCTION(BlueprintPure, Category = "SKYBOUND|Airport Search")
	bool GetResult(int32 ResultIndex, FSkyboundAirport& OutAirport) const;

	/** Runways for the airport at a result index (loads runway data on demand). */
	UFUNCTION(BlueprintCallable, Category = "SKYBOUND|Airport Search")
	bool GetResultRunways(int32 ResultIndex, TArray<FSkyboundRunway>& OutRunways);

	/** Confirm a selection; broadcasts OnAirportChosen. */
	UFUNCTION(BlueprintCallable, Category = "SKYBOUND|Airport Search")
	bool SelectResult(int32 ResultIndex);

	UPROPERTY(BlueprintAssignable, Category = "SKYBOUND|Airport Search")
	FOnSkyboundAirportChosen OnAirportChosen;

	/** Max entries handed to the list widget per query (perf guard). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "SKYBOUND|Airport Search")
	int32 MaxResults = 100;

protected:
	/** Rebuild the visual list from ResultIndices. */
	UFUNCTION(BlueprintImplementableEvent, Category = "SKYBOUND|Airport Search")
	void OnResultsChanged();

	/** Called when the database becomes ready or fails, to switch loading UI. */
	UFUNCTION(BlueprintImplementableEvent, Category = "SKYBOUND|Airport Search")
	void OnDatabaseStateChanged(ESkyboundAirportListState NewState, const FString& Message);

private:
	/** Bound to USkyboundAirportSubsystem::OnDatabaseReady. */
	void HandleDatabaseReady();
	void ApplyFilters();

	UPROPERTY(Transient)
	TObjectPtr<USkyboundAirportSubsystem> AirportSubsystem = nullptr;

	FSkyboundAirportSearchFilter Filter;
	TArray<int32> ResultIndices;

	mutable FString CachedStatus;
};
