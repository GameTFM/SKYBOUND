// SKYBOUND FlightSimulation plugin module.
//
// IMPORTANT LICENSING CONSTRAINT
// ------------------------------
// JSBSim is LGPL-2.1. The Unreal Engine EULA does not permit statically linked
// LGPL code in packaged products, so JSBSim is NOT compiled into this module and
// NOT linked at build time. It is loaded at runtime from a separate DLL that
// ships beside the executable and can be replaced by the user (the LGPL
// relinking requirement). This module therefore has no JSBSim build dependency.

using UnrealBuildTool;

public class FlightSimulation : ModuleRules
{
	public FlightSimulation(ReadOnlyTargetRules Target) : base(Target)
	{
		PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;

		PublicDependencyModuleNames.AddRange(new string[]
		{
			"Core",
			"CoreUObject",
			"Engine"
		});

		// JSBSim ships as an external, replaceable DLL. Its path is resolved at
		// runtime; nothing here links against it.
		PublicDefinitions.Add("SKYBOUND_JSBSIM_DYNAMIC=1");
	}
}
