// SKYBOUND - editor target (development only; never shipped).

using UnrealBuildTool;
using System.Collections.Generic;

public class SKYBOUNDEditorTarget : TargetRules
{
	public SKYBOUNDEditorTarget(TargetInfo Target) : base(Target)
	{
		Type = TargetType.Editor;
		DefaultBuildSettings = BuildSettingsVersion.V5;
		IncludeOrderVersion = EngineIncludeOrderVersion.Unreal5_6;
		ExtraModuleNames.Add("SKYBOUND");
	}
}
