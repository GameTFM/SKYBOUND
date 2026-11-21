// SKYBOUND - JSBSim backend, loaded at runtime.
//
// WHY A C ABI SHIM
// ----------------
// Calling C++ classes across a DLL boundary is fragile (allocator, STL and
// exception mismatches between MSVC runtimes) and it would force every consumer
// to include JSBSim headers, spreading the LGPL surface through the project.
// Instead a small, SKYBOUND-owned shim DLL ("SkbJsbsimShim.dll", built from
// Tools/JSBSimShim) exposes a plain C ABI. That shim is the only code that
// includes JSBSim headers; it is built as a separate, replaceable binary.
//
// If the shim or JSBSim DLL is absent, this backend reports itself unavailable
// with an actionable message. It never pretends to simulate flight.

#include "SkyboundFdmBackend.h"
#include "HAL/PlatformProcess.h"
#include "Misc/Paths.h"

namespace
{
	// --- C ABI exposed by SkbJsbsimShim.dll --------------------------------
	using SkbCreateFn        = void* (*)();
	using SkbDestroyFn       = void  (*)(void*);
	using SkbLoadFn          = int   (*)(void*, const char*, double, double, double, double, int);
	using SkbUnloadFn        = void  (*)(void*);
	using SkbStepFn          = int   (*)(void*, double, const FSKYFdmInputs*);
	using SkbGetStateFn      = int   (*)(void*, FSKYFdmState*);
	using SkbVersionFn       = const char* (*)();

	struct FShimApi
	{
		void* Handle = nullptr;
		SkbCreateFn Create = nullptr;
		SkbDestroyFn Destroy = nullptr;
		SkbLoadFn Load = nullptr;
		SkbUnloadFn Unload = nullptr;
		SkbStepFn Step = nullptr;
		SkbGetStateFn GetState = nullptr;
		SkbVersionFn Version = nullptr;

		bool IsComplete() const
		{
			return Create && Destroy && Load && Unload && Step && GetState && Version;
		}
	};
}

class FJSBSimBackend final : public ISkyboundFdmBackend
{
public:
	FJSBSimBackend()
	{
		ResolveShim();
	}

	virtual ~FJSBSimBackend() override
	{
		if (Api.Handle)
		{
			if (Instance && Api.Destroy)
			{
				Api.Destroy(Instance);
			}
			FPlatformProcess::FreeDllHandle(Api.Handle);
			Api.Handle = nullptr;
		}
	}

	virtual bool IsAvailable() const override { return bAvailable; }

	virtual FString GetUnavailableReason() const override { return UnavailableReason; }

	virtual bool LoadModel(const FString& ModelPath, double LatDeg, double LonDeg,
	                       double AltitudeM, double HeadingDeg, bool bColdAndDark) override
	{
		if (!bAvailable)
		{
			return false;
		}
		if (!Instance)
		{
			Instance = Api.Create();
			if (!Instance)
			{
				UnavailableReason = TEXT("JSBSim shim failed to create an FDM instance.");
				bAvailable = false;
				return false;
			}
		}
		const FTCHARToUTF8 Utf8Path(*ModelPath);
		const int32 Result = Api.Load(Instance, Utf8Path.Get(), LatDeg, LonDeg, AltitudeM,
		                              HeadingDeg, bColdAndDark ? 1 : 0);
		if (Result != 0)
		{
			UnavailableReason = FString::Printf(
				TEXT("JSBSim could not load the aircraft definition: %s (code %d)"),
				*ModelPath, Result);
			return false;
		}
		return true;
	}

	virtual void UnloadModel() override
	{
		if (Instance && Api.Unload)
		{
			Api.Unload(Instance);
		}
	}

	virtual bool Step(double FixedDeltaSeconds, const FSKYFdmInputs& Inputs) override
	{
		return bAvailable && Instance && Api.Step(Instance, FixedDeltaSeconds, &Inputs) == 0;
	}

	virtual bool GetState(FSKYFdmState& OutState) const override
	{
		return bAvailable && Instance && Api.GetState(Instance, &OutState) == 0;
	}

	virtual FString GetBackendVersion() const override
	{
		if (bAvailable && Api.Version)
		{
			return FString(ANSI_TO_TCHAR(Api.Version()));
		}
		return TEXT("JSBSim (unavailable)");
	}

private:
	void ResolveShim()
	{
		// The shim and JSBSim DLL live beside the executable (or in
		// Binaries/Win64 during development) so they can be replaced by the user.
		const FString ShimName = TEXT("SkbJsbsimShim");
		const FString SearchRoot = FPaths::Combine(FPaths::ProjectDir(), TEXT("Binaries"), TEXT("Win64"));

		Api.Handle = FPlatformProcess::GetDllHandle(*FPaths::Combine(SearchRoot, ShimName + TEXT(".dll")));
		if (!Api.Handle)
		{
			Api.Handle = FPlatformProcess::GetDllHandle(*(ShimName + TEXT(".dll")));
		}
		if (!Api.Handle)
		{
			UnavailableReason = FString::Printf(
				TEXT("Flight dynamics unavailable: %s.dll was not found. Build the shim with ")
				TEXT("Scripts/build_jsbsim_shim.ps1 and place it next to the executable. ")
				TEXT("No substitute flight model is used."), *ShimName);
			bAvailable = false;
			return;
		}

		Api.Create    = reinterpret_cast<SkbCreateFn>(FPlatformProcess::GetDllExport(Api.Handle, TEXT("SkbFdmCreate")));
		Api.Destroy   = reinterpret_cast<SkbDestroyFn>(FPlatformProcess::GetDllExport(Api.Handle, TEXT("SkbFdmDestroy")));
		Api.Load      = reinterpret_cast<SkbLoadFn>(FPlatformProcess::GetDllExport(Api.Handle, TEXT("SkbFdmLoad")));
		Api.Unload    = reinterpret_cast<SkbUnloadFn>(FPlatformProcess::GetDllExport(Api.Handle, TEXT("SkbFdmUnload")));
		Api.Step      = reinterpret_cast<SkbStepFn>(FPlatformProcess::GetDllExport(Api.Handle, TEXT("SkbFdmStep")));
		Api.GetState  = reinterpret_cast<SkbGetStateFn>(FPlatformProcess::GetDllExport(Api.Handle, TEXT("SkbFdmGetState")));
		Api.Version   = reinterpret_cast<SkbVersionFn>(FPlatformProcess::GetDllExport(Api.Handle, TEXT("SkbFdmVersion")));

		if (!Api.IsComplete())
		{
			UnavailableReason = TEXT(
				"Flight dynamics unavailable: the JSBSim shim DLL is present but does not export "
				"the expected C ABI. Rebuild it with Scripts/build_jsbsim_shim.ps1.");
			bAvailable = false;
			return;
		}
		bAvailable = true;
	}

	FShimApi Api;
	void* Instance = nullptr;
	bool bAvailable = false;
	FString UnavailableReason;
};

TUniquePtr<ISkyboundFdmBackend> CreateSkyboundFdmBackend()
{
	return MakeUnique<FJSBSimBackend>();
}
