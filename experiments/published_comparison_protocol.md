# Additional comparison protocol

Written before scoring the additional experiments. All eight AIT campaigns have
already been inspected: this remains exploratory, not a new confirmation set.

1. Keep the existing six fitting / one validation / one test campaign folds.
2. Train a three-layer, 32-unit GRU for 18 epochs. Give it the same causal
   current / trailing 5, 15 and 60-minute count summaries as boosting, presented
   in 30-minute sequences. Scaling and vocabulary use fitting campaigns only.
   Keep the previous deterministic seed, optimizer, positive weighting and
   fitting-bin sample. Select epoch 6, 12 or 18 using mean validation AP at
   15 and 30 minutes, breaking ties toward the earlier epoch. Test predictions
   are generated only after selecting the checkpoint. Apply the existing
   validation calibration and alarm selection. This is a stronger bounded
   same-task GRU comparison, **not an Ansari2022 reproduction**: that paper
   predicts next Warden alert tuples and uses substantially different training.
   Validation is reused for selection and calibration; disclose that limitation.
3. Using saved predictions, select alarm thresholds separately on the validation
   campaign for budgets 0, 0.25, 1 and 4 false episodes per 24 negative hours,
   retaining the five negative warning-minute limit. Optimize *new episode
   starts* inside the forecast window, then lead, then smaller alarm burden.
   Freeze these thresholds before scoring scheduled and audited root endpoints
   of the test campaign. Inspect 15 and 30 minutes for every available model.
   A validation budget is not a guarantee of the test alarm rate.
4. Retrieve and hash a pinned author PARD-SSM source snapshot. Review imports
   before executing its filter. Check prefix invariance of regime probabilities
   and distinguish retrospective Viterbi output. Audit the public experiment's
   preprocessing, training and forecast output against the paper. Exclude it
   from a full-system leaderboard if a compatible first-onset implementation
   cannot be reproduced. Do not silently invent the missing components.
5. Independently recompute scores and split/checkpoint choices. Report all
   outcomes, including worse probability scores, missed targets, campaign
   dependence, external failure and assumed response costs. Compare publications
   only with compatible targets and protocols; different accuracy definitions
   cannot establish superiority.

Outputs are in `experiments/published_comparison`; original experiments remain
available. The pipeline still covers Unit 1 Bayesian inference, Unit 2 HMM
filtering and Unit 3 Decision Networks. A comparator does not replace that
pipeline or establish a novel algorithm.
