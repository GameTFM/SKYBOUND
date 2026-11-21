// SKYBOUND - primary runtime module.

using UnrealBuildTool;

public class SKYBOUND : ModuleRules
{
	public SKYBOUND(ReadOnlyTargetRules Target) : base(Target)
	{
		PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;

		PublicDependencyModuleNames.AddRange(new string[]
		{
			"Core",
			"CoreUObject",
			"Engine",
			"InputCore",
			"EnhancedInput",
			"Json",
			"JsonUtilities",
			"Niagara",
			"GeometryCore"
		});

		PrivateDependencyModuleNames.AddRange(new string[]
		{
			"Slate",
			"SlateCore",
			"RenderCore",
			"RHI",
			"ApplicationCore",
			"AudioMixer",
			"Projects",
			"DeveloperSettings"
		});

		// Cesium provides the geospatial world (Cesium for Unreal is a plugin with
		// its own module names; these are its runtime modules).
		PrivateDependencyModuleNames.AddRange(new string[]
		{
			"CesiumRuntime"
		});

		// The flight model lives behind the FlightSimulation plugin so that the
		// LGPL JSBSim boundary is isolated in exactly one module.
		PrivateDependencyModuleNames.Add("FlightSimulation");
	}
}
