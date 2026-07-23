# Third-Party Notices

This Skill minimally adapts workflow ideas, controlled vocabularies, and checklists from the
following public Agent Skills. Upstream repositories are not vendored. Runtime behavior and
schemas in this package are rewritten for the local seven-stage contract.

## Sources

1. **product-video-analysis**
   - Repository: https://github.com/zhanziyang/product-video-analysis-skill
   - Commit: `a913ea334e5dae70b6104e096ff37585e3a26e06`
   - License: MIT
   - Used for: evidence labeling, measure-before-interpret, complete motion/audio coverage.

2. **storyboard-architect**
   - Repository: https://github.com/whystrohm/shotkit
   - Commit: `673ee9967efe941d6d8dcfe029694e330a48d198`
   - License: Apache-2.0
   - Used for: deterministic shot contracts, timing, controlled shot vocabulary, rationale.

3. **visual-prompt-forge**
   - Repository: https://github.com/whystrohm/shotkit
   - Commit: `673ee9967efe941d6d8dcfe029694e330a48d198`
   - License: Apache-2.0
   - Used for: series locks, per-shot visual prompt anatomy, QA correction loop.

4. **image**
   - Repository: https://github.com/smixs/visual-skills
   - Commit: `50905021f4243df27e34cb42c7ae263c03d9306a`
   - License: MIT
   - Used for: image-generation constraints and visual inspection discipline.

5. **ecommerce-visual-copywriting-skill**
   - Repository: https://github.com/feichanggege/ecommerce-visual-copywriting-skill
   - Commit: `38736d1ca30ee3b96d7015a16594e6c351ec3610`
   - License: MIT
   - Used for: product-fact boundaries, missing-information handling, ecommerce compliance.

6. **seedance-prompt**
   - Repository: https://github.com/rich5000/seedance-prompt-guide
   - Commit: `1dbdd80db24e934963920e09c51e20653eee0125`
   - License: MIT
   - Used for: timeline-first Seedance prompt structure, visible actions, camera and sound cues.

Exact upstream commits are intentionally pinned. Updates are manual and require review against
the JSON contracts in this package.

Full license texts are stored in `licenses/`.
