// SKYBOUND - packaged game target.
// UE 5.6 is the chosen baseline: it is the oldest Unreal version still supported
// by Cesium for Unreal v2.31 (which supports 5.6 / 5.7 / 5.8 only). Choosing the
// oldest supported version maximises third-party plugin compatibility.

using UnrealBuildTool;
using System.Collections.Generic;

public class SKYBOUNDTarget : TargetRules
{
	public SKYBOUNDTarget(TargetInfo Target) : base(Target)
	{
		Type = TargetType.Game;
		DefaultBuildSettings = BuildSettingsVersion.V5;
		IncludeOrderVersion = EngineIncludeOrderVersion.Unreal5_6;
		ExtraModuleNames.Add("SKYBOUND");

		// Shipping builds must not contain debug tooling (spec 20).
		if (Configuration == UnrealTargetConfiguration.Shipping)
		{
			bUseLoggingInShipping = false;
			bCompileWithStatsWithoutEngine = false;
		}
	}
}
