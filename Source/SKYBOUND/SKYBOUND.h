// SKYBOUND - module header.

#pragma once

#include "CoreMinimal.h"
#include "Modules/ModuleManager.h"

/**
 * Device-level log categories. Keeping them separate lets QA filter a crash log
 * by subsystem (spec 24, 26.15).
 */
DECLARE_LOG_CATEGORY_EXTERN(LogSkybound, Log, All);
DECLARE_LOG_CATEGORY_EXTERN(LogSkyboundFdm, Log, All);
DECLARE_LOG_CATEGORY_EXTERN(LogSkyboundCatalog, Log, All);
DECLARE_LOG_CATEGORY_EXTERN(LogSkyboundStreaming, Log, All);
DECLARE_LOG_CATEGORY_EXTERN(LogSkyboundSave, Log, All);

class FSKYBOUNDModule : public IModuleInterface
{
public:
	virtual void StartupModule() override;
	virtual void ShutdownModule() override;
};
