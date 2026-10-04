# Exploratory fusion hypothesis

Declared 4 October 2026 after inspecting six folds of the extended AIT study.
This is a new development hypothesis, not a preregistered success claim.

The informative detector-count boosted baseline gives better prospective
ranking than the generative models in several runs. Test whether a learned
conditional probability model can combine its forecast with duration-HMM
risk without treating correlated predictions as independent evidence.

For every existing outer split, generate two disjoint three-scenario inner
fits within the six fitting scenarios. Predict the opposite three scenarios
to obtain out-of-scenario training predictions from both base models.
Fit a regularized logistic conditional probability distribution for the
future-onset chance node with the two logit forecasts as parents, C=1.
Refit both base models on all six fitting runs, then use that frozen
conditional model on outer validation/test runs. Calibrate on the existing
validation run. Never fit fusion weights on held-out test outcomes.

This is conventional stacking expressed as a conditional probabilistic
model, not a newly invented Bayesian inference principle. Compare against
the boosted baseline, duration model and equal-weight probability fusion
under the same data, horizon, warning rule and response assumptions.
Keep results even if the combination loses. Reusing these datasets for
method development means a fresh independent benchmark is still needed.
