// SKYBOUND - module implementation.

#include "SKYBOUND.h"

DEFINE_LOG_CATEGORY(LogSkybound);
DEFINE_LOG_CATEGORY(LogSkyboundFdm);
DEFINE_LOG_CATEGORY(LogSkyboundCatalog);
DEFINE_LOG_CATEGORY(LogSkyboundStreaming);
DEFINE_LOG_CATEGORY(LogSkyboundSave);

void FSKYBOUNDModule::StartupModule()
{
	UE_LOG(LogSkybound, Log, TEXT("SKYBOUND runtime module started"));
}

void FSKYBOUNDModule::ShutdownModule()
{
	UE_LOG(LogSkybound, Log, TEXT("SKYBOUND runtime module stopped"));
}

IMPLEMENT_PRIMARY_GAME_MODULE(FSKYBOUNDModule, SKYBOUND, "SKYBOUND");
