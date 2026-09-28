# Third-Party Notices

This document lists third-party content bundled in this repository and the licence terms that apply to each part. It covers the Unity project at `unity/SBGamesMLAgents/`.

## 1. Author's own work

The following paths are the author's (Lucas Brandao's) own work, under this repository's MIT licence (`LICENSE`): `unity/SBGamesMLAgents/Assets/Basic`, with the exceptions below, and the scripts and configuration files in this repository outside the third-party paths listed in this document. The documentation and teaching materials (`README.md` and `docs/`) are under the Creative Commons Attribution 4.0 International licence (`LICENSE-docs`). `unity/SBGamesMLAgents/Assets/FlappyBird` is a mix of third-party and own work; see section 4. The scene `Assets/Basic/Scenes/Basic.unity` was built starting from the ML-Agents example scene `Examples/Basic/Scenes/Basic.unity` (Apache License, Version 2.0, same source as section 2), and the prefab `Assets/Basic/Prefabs/Basic - Lucas.prefab` was made from the `Basic` object of that scene, as the author's 2024 thesis describes. The Basic environment follows the Code Monkey tutorial video `https://www.youtube.com/watch?v=zPFU30tbyKs`, as the thesis also states; its scripts were not compared with the tutorial's own project files.

## 2. Unity ML-Agents example assets

Copyright Unity Technologies. Licensed under the Apache License, Version 2.0. Source: `https://github.com/Unity-Technologies/ml-agents/tree/release_22/Project/Assets/ML-Agents/Examples/SharedAssets`.

The following files under `unity/SBGamesMLAgents/Assets/SharedAssets/` are copied from that source, each together with its Unity `.meta` companion file:

- `Materials/AgentBlue.mat`
- `Materials/Black.mat`
- `Materials/Eye.mat`
- `Materials/Green.mat`
- `Materials/GridMatFloor.mat`
- `Materials/GridPatternShader.shader`
- `Materials/Headband.mat`
- `Materials/LogoSymbol.mat`
- `Materials/Textures/LogoCube.png`
- `Materials/Textures/U_Logo_White_RGB.png`
- `Prefabs/Canvas_Watermark.prefab`
- `Prefabs/Directional_Light.prefab`
- `Scripts/ProjectSettingsOverrides.cs`

Script changes for Unity 6.3: `Scripts/ProjectSettingsOverrides.cs` is unmodified. It is byte identical to the upstream `release_22` source, verified by diffing it against `sources/tcc-repo/Project/Assets/SharedAssets/Scripts/ProjectSettingsOverrides.cs` (the 2024 thesis repository, itself a fork of `release_22`), which shows no differences.

The Apache License, Version 2.0 full text follows. The `LICENSE.md` file in the ml-agents repository at that source URL is a short notice pointing to this licence rather than the full text, so the text below was instead fetched from `https://www.apache.org/licenses/LICENSE-2.0.txt`.

```
                                 Apache License
                           Version 2.0, January 2004
                        http://www.apache.org/licenses/

   TERMS AND CONDITIONS FOR USE, REPRODUCTION, AND DISTRIBUTION

   1. Definitions.

      "License" shall mean the terms and conditions for use, reproduction,
      and distribution as defined by Sections 1 through 9 of this document.

      "Licensor" shall mean the copyright owner or entity authorized by
      the copyright owner that is granting the License.

      "Legal Entity" shall mean the union of the acting entity and all
      other entities that control, are controlled by, or are under common
      control with that entity. For the purposes of this definition,
      "control" means (i) the power, direct or indirect, to cause the
      direction or management of such entity, whether by contract or
      otherwise, or (ii) ownership of fifty percent (50%) or more of the
      outstanding shares, or (iii) beneficial ownership of such entity.

      "You" (or "Your") shall mean an individual or Legal Entity
      exercising permissions granted by this License.

      "Source" form shall mean the preferred form for making modifications,
      including but not limited to software source code, documentation
      source, and configuration files.

      "Object" form shall mean any form resulting from mechanical
      transformation or translation of a Source form, including but
      not limited to compiled object code, generated documentation,
      and conversions to other media types.

      "Work" shall mean the work of authorship, whether in Source or
      Object form, made available under the License, as indicated by a
      copyright notice that is included in or attached to the work
      (an example is provided in the Appendix below).

      "Derivative Works" shall mean any work, whether in Source or Object
      form, that is based on (or derived from) the Work and for which the
      editorial revisions, annotations, elaborations, or other modifications
      represent, as a whole, an original work of authorship. For the purposes
      of this License, Derivative Works shall not include works that remain
      separable from, or merely link (or bind by name) to the interfaces of,
      the Work and Derivative Works thereof.

      "Contribution" shall mean any work of authorship, including
      the original version of the Work and any modifications or additions
      to that Work or Derivative Works thereof, that is intentionally
      submitted to Licensor for inclusion in the Work by the copyright owner
      or by an individual or Legal Entity authorized to submit on behalf of
      the copyright owner. For the purposes of this definition, "submitted"
      means any form of electronic, verbal, or written communication sent
      to the Licensor or its representatives, including but not limited to
      communication on electronic mailing lists, source code control systems,
      and issue tracking systems that are managed by, or on behalf of, the
      Licensor for the purpose of discussing and improving the Work, but
      excluding communication that is conspicuously marked or otherwise
      designated in writing by the copyright owner as "Not a Contribution."

      "Contributor" shall mean Licensor and any individual or Legal Entity
      on behalf of whom a Contribution has been received by Licensor and
      subsequently incorporated within the Work.

   2. Grant of Copyright License. Subject to the terms and conditions of
      this License, each Contributor hereby grants to You a perpetual,
      worldwide, non-exclusive, no-charge, royalty-free, irrevocable
      copyright license to reproduce, prepare Derivative Works of,
      publicly display, publicly perform, sublicense, and distribute the
      Work and such Derivative Works in Source or Object form.

   3. Grant of Patent License. Subject to the terms and conditions of
      this License, each Contributor hereby grants to You a perpetual,
      worldwide, non-exclusive, no-charge, royalty-free, irrevocable
      (except as stated in this section) patent license to make, have made,
      use, offer to sell, sell, import, and otherwise transfer the Work,
      where such license applies only to those patent claims licensable
      by such Contributor that are necessarily infringed by their
      Contribution(s) alone or by combination of their Contribution(s)
      with the Work to which such Contribution(s) was submitted. If You
      institute patent litigation against any entity (including a
      cross-claim or counterclaim in a lawsuit) alleging that the Work
      or a Contribution incorporated within the Work constitutes direct
      or contributory patent infringement, then any patent licenses
      granted to You under this License for that Work shall terminate
      as of the date such litigation is filed.

   4. Redistribution. You may reproduce and distribute copies of the
      Work or Derivative Works thereof in any medium, with or without
      modifications, and in Source or Object form, provided that You
      meet the following conditions:

      (a) You must give any other recipients of the Work or
          Derivative Works a copy of this License; and

      (b) You must cause any modified files to carry prominent notices
          stating that You changed the files; and

      (c) You must retain, in the Source form of any Derivative Works
          that You distribute, all copyright, patent, trademark, and
          attribution notices from the Source form of the Work,
          excluding those notices that do not pertain to any part of
          the Derivative Works; and

      (d) If the Work includes a "NOTICE" text file as part of its
          distribution, then any Derivative Works that You distribute must
          include a readable copy of the attribution notices contained
          within such NOTICE file, excluding those notices that do not
          pertain to any part of the Derivative Works, in at least one
          of the following places: within a NOTICE text file distributed
          as part of the Derivative Works; within the Source form or
          documentation, if provided along with the Derivative Works; or,
          within a display generated by the Derivative Works, if and
          wherever such third-party notices normally appear. The contents
          of the NOTICE file are for informational purposes only and
          do not modify the License. You may add Your own attribution
          notices within Derivative Works that You distribute, alongside
          or as an addendum to the NOTICE text from the Work, provided
          that such additional attribution notices cannot be construed
          as modifying the License.

      You may add Your own copyright statement to Your modifications and
      may provide additional or different license terms and conditions
      for use, reproduction, or distribution of Your modifications, or
      for any such Derivative Works as a whole, provided Your use,
      reproduction, and distribution of the Work otherwise complies with
      the conditions stated in this License.

   5. Submission of Contributions. Unless You explicitly state otherwise,
      any Contribution intentionally submitted for inclusion in the Work
      by You to the Licensor shall be under the terms and conditions of
      this License, without any additional terms or conditions.
      Notwithstanding the above, nothing herein shall supersede or modify
      the terms of any separate license agreement you may have executed
      with Licensor regarding such Contributions.

   6. Trademarks. This License does not grant permission to use the trade
      names, trademarks, service marks, or product names of the Licensor,
      except as required for reasonable and customary use in describing the
      origin of the Work and reproducing the content of the NOTICE file.

   7. Disclaimer of Warranty. Unless required by applicable law or
      agreed to in writing, Licensor provides the Work (and each
      Contributor provides its Contributions) on an "AS IS" BASIS,
      WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
      implied, including, without limitation, any warranties or conditions
      of TITLE, NON-INFRINGEMENT, MERCHANTABILITY, or FITNESS FOR A
      PARTICULAR PURPOSE. You are solely responsible for determining the
      appropriateness of using or redistributing the Work and assume any
      risks associated with Your exercise of permissions under this License.

   8. Limitation of Liability. In no event and under no legal theory,
      whether in tort (including negligence), contract, or otherwise,
      unless required by applicable law (such as deliberate and grossly
      negligent acts) or agreed to in writing, shall any Contributor be
      liable to You for damages, including any direct, indirect, special,
      incidental, or consequential damages of any character arising as a
      result of this License or out of the use or inability to use the
      Work (including but not limited to damages for loss of goodwill,
      work stoppage, computer failure or malfunction, or any and all
      other commercial damages or losses), even if such Contributor
      has been advised of the possibility of such damages.

   9. Accepting Warranty or Additional Liability. While redistributing
      the Work or Derivative Works thereof, You may choose to offer,
      and charge a fee for, acceptance of support, warranty, indemnity,
      or other liability obligations and/or rights consistent with this
      License. However, in accepting such obligations, You may act only
      on Your own behalf and on Your sole responsibility, not on behalf
      of any other Contributor, and only if You agree to indemnify,
      defend, and hold each Contributor harmless for any liability
      incurred by, or claims asserted against, such Contributor by reason
      of your accepting any such warranty or additional liability.

   END OF TERMS AND CONDITIONS

   APPENDIX: How to apply the Apache License to your work.

      To apply the Apache License to your work, attach the following
      boilerplate notice, with the fields enclosed by brackets "[]"
      replaced with your own identifying information. (Don't include
      the brackets!)  The text should be enclosed in the appropriate
      comment syntax for the file format. We also recommend that a
      file or class name and description of purpose be included on the
      same "printed page" as the copyright notice for easier
      identification within third-party archives.

   Copyright [yyyy] [name of copyright owner]

   Licensed under the Apache License, Version 2.0 (the "License");
   you may not use this file except in compliance with the License.
   You may obtain a copy of the License at

       http://www.apache.org/licenses/LICENSE-2.0

   Unless required by applicable law or agreed to in writing, software
   distributed under the License is distributed on an "AS IS" BASIS,
   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
   See the License for the specific language governing permissions and
   limitations under the License.
```

## 3. Unity packages

This project consumes `com.unity.ml-agents` 4.1.0, `com.unity.ai.inference` 2.6.1, and other packages from the Unity package registry under their own licence terms. Nothing from these packages is vendored in this repository; the Unity Package Manager downloads them on first open of the project. `com.unity.nuget.newtonsoft-json` wraps Newtonsoft.Json (MIT licence) and is likewise fetched by the Package Manager, not shipped in this repository.

## 4. FlappyBird game (`Assets/FlappyBird`)

The FlappyBird game in `unity/SBGamesMLAgents/Assets/FlappyBird/` derives from Dimitris Gkanatsios's "FlappyBirdStyleGame" (`https://github.com/dgkanatsios/FlappyBirdStyleGame`).

Unchanged copies of that repository's files: `Animations/flappyAnimation.anim`, `Animations/sprites_58.controller`, `Sprites/sprites.png`, `Sounds/death.mp3`, `Sounds/fly.mp3`, `Sounds/scored.mp3`, the folder metas `Animations.meta`, `Prefabs.meta`, `Scenes.meta`, `Scripts.meta`, `Sounds.meta`, `Sprites.meta`, and the `.meta` file of every upstream file named in this section except `Sprites/sprites.png.meta`.

Modified copies of that repository's files: `Scripts/Game/CameraFollow.cs`, `Scripts/Game/FlappyScript.cs`, `Scripts/Game/FloorMoveScript.cs`, `Scripts/Game/GameState.cs`, `Scripts/Game/PipeDestroyerScript.cs`, `Scripts/Game/RandomBackgroundScript.cs`, `Scripts/Game/ScoreManagerScript.cs`, `Scripts/Game/SpawnerScript.cs`, `Prefabs/PipeColumnPrefab.prefab`, `Prefabs/PipeColumnPrefab2.prefab`, `Scenes/mainGame.unity`, and `Sprites/sprites.png.meta` (same GUID, re-imported by a newer Unity). Three lines of `FloorMoveScript.cs` were contributed upstream by GitHub user `Cosebdd` (pull request #3, merged 2021-10-03).

The author's (Lucas Brandao's) own work: `Scripts/MLAgents/FlappyAgent.cs`, `Demos/Level1FlappyAgentDemo.demo`, `Demos/Leve2FlappyAgentDemo.demo`, `TFModels/FlappyAgentLevel1.onnx`, `TFModels/FlappyAgentLevel2.onnx`, `TFModels/FlappyAgentLevel3.onnx`, their `.meta` files, the folder metas `Demos.meta`, `Scripts/Game.meta`, `Scripts/MLAgents.meta` and `TFModels.meta`, and the ML-Agents additions inside the modified files listed above. `FlappyAgent.cs` follows the Code Monkey tutorial video "AI Learns to play Flappy Bird!" (`https://www.youtube.com/watch?v=fz8D0OZkQGQ`), as the author's 2024 thesis states; it was not compared with that tutorial's project files.

The `dgkanatsios/FlappyBirdStyleGame` repository has no licence file. In its GitHub issue #2, "Licence" (opened 2017-06-28), a user asked for permission to adapt and use the game for educational purposes, and the author replied on 2017-06-28: "Hi @pixele, thanks for reaching out. Of course, feel free to use the code for whatever purpose you wish." (`https://github.com/dgkanatsios/FlappyBirdStyleGame/issues/2`). The upstream author's own files listed above (the scripts, animations, prefabs, scene and `.meta` files) are used under this public statement. The sprite sheet and the sounds are not his work, so the statement does not cover them; see the next two paragraphs. None of the files listed above under that repository is covered by this repository's MIT licence.

`Sprites/sprites.png` is byte identical to The Spriters Resource asset 59894, "Version 1.2 Sprites" (`https://www.spriters-resource.com/mobile/flappybird/sheet/59894/`), not to sheet 59537. The site's Terms of Use (last updated 2025-03-31) state: "Taking content in its original format from this website and distributing it elsewhere without prior consent or credit to its origin will also result in contact being made with those seen fit to have it removed as this is also viewed as theft. Use of the content of this site is not included in this term, as that is the purpose of this resource. Feel free to use the content as you wish (where legally permitted or in unpublished, non-commercial works)." and "Content on these sites may not be used in any commercial works." The header comment inside `Scripts/Game/FlappyScript.cs` cites sheet 59537 instead. That citation comes from the upstream project, which did not update it when the sprite file was added in 2015.

`Sounds/death.mp3`, `Sounds/fly.mp3` and `Sounds/scored.mp3` came with the upstream repository, and their earlier origin is unknown. The audio credit in the header of `Scripts/Game/FlappyScript.cs`, The Sounds Resource page 5309, was added upstream in 2018. That page was submitted in 2015, after the files were first committed in 2014, and its files are not the source of these MP3s.

The third-party files listed in this section belong to their original authors and are included in this repository only for educational use in this tutorial.
