# Literature audit of the proposed attack-forecasting pipeline

Audit date: 4 October 2026. Scope: academic originality of the design in [RESEARCH_PIPELINE.md](RESEARCH_PIPELINE.md), with reference to the existing implementation. This is an evidence-based assessment of accessible literature, not a guarantee that every relevant publication has been found.

## Verdict

**Publication-validation update:** Original execution and victim audit logs now
verify the privilege endpoint in all eight AIT campaigns. A stricter warning
definition gives 4/8 timely new alarms for both tree and learned fusion, rather
than counting a persistent earlier alarm toward the 5/8 any-warning figure.
The 30-minute false-alarm total still decreases from 20 to 5, but after removing
wheeler it increases from 3 to 4. Bounded published-method adaptations and a
three-layer GRU have been evaluated with the same outer splits. An untouched
CAM-LDS transfer diagnostic gives 0/3 warnings with missing input sources and
short recordings. These findings strengthen auditability, not a universal
superiority claim. See [the supplemental report](../experiments/publication_validation/REPORT.md).

**Extended empirical update:** Learned duration-HMM/tree fusion now has measured
warning tradeoffs relative to the stronger tree baseline, including 5 rather
than 20 false-warning episodes at the same 5/8 30-minute AIT coverage. Its
15/30-minute probability error worsens and the alarm reduction concentrates in
one campaign. Suricata removal preserves 5/8 warnings versus 3/8 for the tree,
but AMiner/Wazuh removal defeats both. These are exploratory empirical findings,
not evidence of a new inference principle. See the
[complete extended report](../experiments/extended_study/REPORT.md).

**Empirical update, 4 October 2026:** The first bounded probabilistic association prototype has now been tested on eight AIT-ADS scenarios. It gives mixed results and does not establish a convincing forecasting advantage over ordinary exact deduplication. Some ranking improvements, especially under constructed duplicate stress, warrant further investigation but do not establish originality. See [the full pilot report](../experiments/evidence_pilot/REPORT.md). This experiment forecasts scheduled privilege escalation and does not validate DDoS prediction.

**The proposed architecture has substantial published precedents. Its originality is currently unestablished. Do not describe BN + HMM + Decision Network, early attack prediction, duplicate handling, or forecast-based response as first-ever contributions.**

No inspected source was verified to implement every detail of our proposed combination: provenance-aware evidence grouping, a single BN evidence likelihood in temporal filtering, calibrated clock-based first-onset forecasts, and a Decision Network with response delays. That is a search finding, not proof that the combination is original. Several publications already combine closely related functions using different model names.

A useful combination of established methods can support a paper when it contributes a distinct method, a convincing empirical finding, or both. An apparent improvement over separately reported accuracy figures is insufficient: compare all methods on the same forecasting task, data split, information, and tuning budget. The expanded study demonstrates narrow gains against standard component/feature baselines, while superiority to complete named published systems remains unestablished.

## What was checked

The audit covered both the named models and functional equivalents: Bayesian/causal attack networks, dynamic Bayesian networks, hidden and continuous-time Markov models, state-space forecasting, alert correlation and aggregation, reliability-weighted evidence, partially observable decision processes, influence diagrams, security games, and cost-sensitive intrusion response. Older work and indexed 2026 publications/preprints were included.

Discovery used web searches, publisher pages, author/institution repositories, bibliographic records, and references from relevant papers. Technical conclusions below rely on primary papers, publisher descriptions, or institutional publication records. Third-party copies and reviews were useful for discovery but were not treated as verified primary methods.

Representative search expressions included:

- `cyber attack Bayesian network hidden Markov decision network prediction`
- `intrusion prediction Bayesian HMM response utility`
- `attack forecasting first passage Markov`
- `cyber attack time-to-compromise Bayesian prediction`
- `intrusion prediction double counting evidence`
- `cyber attack prediction correlated evidence Bayesian`
- `attack prediction duplicate hidden Markov`
- `cybersecurity attack forecasting calibrated probabilities horizons`
- `intrusion response deadline partially observable`
- Exact-title searches for the sources below, followed by PDF, author, publisher, and repository searches.

This was not an exhaustive export and screening of Scopus/Web of Science. Publisher blocking, unavailable full texts, incomplete indexing, and unpublished work limit coverage. An inaccessible paper is an unresolved comparison, never evidence that it lacks a feature. Search-engine publication/crawl dates were not used as paper publication dates when the source supplied a date.

## Claim-by-claim assessment

| Proposed claim | Evidence assessment | Consequence for our paper |
|---|---|---|
| Combine Bayesian networks and HMMs for cyber analysis | Explicit combinations exist: Devarakonda et al. (2012), Li et al. (2020). | Model pairing alone does not establish novelty. |
| Infer an uncertain hidden threat state from evidence and propagate it over time | eBayes (2000) already combines Bayesian updates and Markov propagation. | A correct likelihood/filter interface is necessary modeling, not a new inference principle. |
| Avoid treating many reports as many independent incidents | Valdes and Skinner (2001) fuse reports into incidents; Pivarníková et al. (2020) aggregate redundant alerts before BN prediction. | Ordinary deduplication/aggregation must be a baseline. |
| Incorporate sensor reliability and control false alarms | Tabia and Leray (2010) use virtual evidence and a reject option for severe-attack prediction. | Generic reliability-aware Bayesian evidence is established. |
| Predict a later harmful stage before it occurs | DIPS (2007), Sendi et al. (2012), Li et al. (2020), and PARD-SSM (2026 preprint) address prospective attack behavior. | Define a narrower endpoint and prediction protocol; early prediction alone is established. |
| Advance state estimates using elapsed time | eBayes adjusts persistence for elapsed time; Lefebvre et al. (2022) explicitly use observation timestamps in continuous-time Markov estimation. | Clock handling alone is established. |
| Choose countermeasures from probabilities and costs | Poolsappasit et al. (2012), Codetta-Raiteri et al. (2014/2018), RRE (2014). | Expected-utility response is established. |
| Use predicted future threats when deciding responses | DIPS (2007), RRE (2014), GhasemiGol et al. (2016), and the 2026 Stackelberg study. | Forecast-to-response coupling alone is established. |
| Calibrate cyber-risk forecasts and assess intervention costs | ProSpaCT (September 2026 preprint), according to its primary abstract. | Calibration plus operational decisions is also an occupied research direction. |
| The complete particular integration performs better under shared/repeated evidence and timing changes | No exact full match verified. Follow-up experiments measure conditional warning tradeoffs; a robust gain from the association prototype is not demonstrated. | Exploratory empirical contribution with narrower claims. Originality and general superiority remain unresolved. |

Rows indicate confirmed overlap in the stated function; they do not claim that these papers share identical mathematics, endpoints, datasets, or implementations.

## Evidence register and access status

### 1. Adaptive, Model-based Monitoring for Cyber Attack Detection — Valdes and Skinner, RAID 2000

[SRI publication record](https://www.csl.sri.com/papers/adaptbn/) and [author-hosted full text](https://www.csl.sri.com/papers/adaptbn/adaptbn.html).

**Access:** Full HTML available; inference and transition sections inspected. Bayesian likelihood updates follow a Markov prediction of the previous posterior. Inference intervals can reflect events or elapsed time. The transition discussion explicitly adjusts persistence when thousands of DoS events arrive in little time. This strongly overlaps coherent temporal Bayesian inference and elapsed-time handling. Its documented task is attack detection; our specific calibrated first-onset/response combination was not verified here.

### 2. Probabilistic Alert Correlation — Valdes and Skinner, RAID 2001

[SRI paper, PDF](https://www.csl.sri.com/papers/raid2001-pac/prob_corr.pdf).

**Access:** Full PDF available; correlation and example sections inspected. Reports are grouped into threads, incidents, and multistep scenarios, including cross-sensor reports of the same attack. Matching accommodates timing differences and sensor identity. This is strong precedent for evidence grouping. It does not establish that its fusion is our proposed probabilistic correction for overlapping likelihoods.

### 3. DIPS: A Framework for Distributed Intrusion Prediction and Prevention Using Hidden Markov Models and Online Fuzzy Risk Assessment — Haslum, Abraham, Knapskog, 2007

[Primary proceedings record and abstract](https://eudl.eu/doi/10.1109/ias.2007.67). DOI: 10.1109/IAS.2007.67.

**Access:** Abstract verified; author PDF retrieval unsuccessful. HMM one-step predictions and asset risk activate preventive responses, including blocking. It directly precedes the broad predict-then-prevent objective. Fuzzy risk assessment differs from our explicit Decision Network, and its calibrated clock horizons and evidence-overlap behavior remain unverified. A conflicting DOI in a secondary reference was not adopted.

### 4. Handling IDS' Reliability in Alert Correlation — Tabia and Leray, SECRYPT 2010

[Publisher full text](https://www.scitepress.org/PublishedPapers/2010/29498/pdf/index.html). DOI: 10.5220/0002949800140024.

**Access:** Full publisher text available; Sections 5–7 inspected. Reliability is incorporated through Pearl's virtual evidence; uncertain classifications can be rejected to control severe-attack prediction/false-alarm tradeoffs. This is close precedent for reliability-aware precursor reasoning. Rejecting uncertain predictions does not itself establish our forecast-based countermeasure policy.

### 5. Intrusion Detection System using Bayesian Network and Hidden Markov Model — Devarakonda et al., 2012

[Publisher article](https://www.sciencedirect.com/science/article/pii/S221201731200360X). DOI: 10.1016/j.protcy.2012.05.081.

**Access:** Indexed publisher abstract; direct retrieval blocked. It explicitly combines BN and HMM for intrusion detection, with the BN structure used in the HMM representation. This refutes a generic first-ever pairing claim. It does not prove identical BN-to-HMM likelihood semantics or prospective onset forecasting. Full method comparison remains open.

### 6. Real Time Intrusion Prediction based on Optimized Alerts with Hidden Markov Model — Shameli-Sendi, Dagenais, Jabbarifar, Couture, 2012

[Original paper indexed in CiteSeerX](https://citeseerx.ist.psu.edu/document?doi=3aa6e5a9a9bfb27bf32fbab8b2c194ab42bad1dc&repid=rep1&type=pdf). DOI: 10.4304/jnw.7.2.311-321.

**Access:** Original-paper abstract and limited indexed text; direct PDF/DOI retrieval unsuccessful. Alert optimization feeds HMM multistep prediction to help responses before compromise. A third-party transcription suggests stronger DARPA/DDoS and response-cost overlap, but those details require primary full-text verification and are not used as confirmed findings. This paper is a high-priority baseline/comparison.

### 7. Dynamic Security Risk Management Using Bayesian Attack Graphs — Poolsappasit, Dewri, Ray, TDSC 2012

[Author/institution-hosted paper](https://www.cs.colostate.edu/psysec/papers/Dynamic%20Security%20Risk%20Management%20Using%20Bayesian%20Attack%20Graphs.pdf). DOI: 10.1109/TDSC.2011.34; journal issue 2012, online 2011.

**Access:** Full PDF available; evidence-update and mitigation sections inspected. Bayesian attack graphs update risk from evidence, reason about future consequences, and select controls using expected loss/gain and implementation costs. Its optimization differs from a streaming BN-HMM onset forecaster, but Bayesian risk plus cost-sensitive proactive response is established.

### 8. RRE: A Game-Theoretic Intrusion Response and Recovery Engine — Zonouz et al., TPDS 2014

[Institutional publication record](https://experts.illinois.edu/en/publications/rre-a-game-theoretic-intrusion-response-and-recovery-engine/). DOI: 10.1109/TPDS.2013.211; issue February 2014. An earlier conference version appeared in 2009.

**Access:** Institutional abstract and metadata verified; journal full text not verified. Uncertain IDS alerts feed a partially observable competitive Markov decision process; responses consider current and possible future security states. This is a strong functional precedent even though its model labels differ. Our exact first-onset calibration and overlap control are unresolved comparisons.

### 9. Decision Networks for Modeling and Analysis of Attack/Defense Scenarios in Critical Infrastructures — Codetta-Raiteri, Portinale, Terruggia, FLAIRS 2014

[Publisher-hosted full paper](https://cdn.aaai.org/ocs/7778/7778-36697-1-PB.pdf).

**Access:** Full four-page PDF available; decision and cost sections inspected. Decision Networks model attacks, countermeasures, uncertainty, and expected costs to select defenses. This directly precedes our Unit 3 component. A related journal paper, [Decision Networks for Security Risk Assessment of Critical Infrastructures](https://doi.org/10.1145/3137570), appeared in 2018; its publisher abstract was verified, not its complete methods.

### 10. A comprehensive approach for network attack forecasting — GhasemiGol, Ghaemi-Bafghi, Takabi, 2016

[Publisher preview](https://www.sciencedirect.com/science/article/abs/pii/S0167404815001819). DOI: 10.1016/j.cose.2015.11.005; issue May 2016.

**Access:** Indexed abstract, introduction, and section snippets; complete methods not verified. Forecasting uses uncertain attack probabilities, IDS alerts, active responses, and network dependencies. This precedes the general integration of uncertain evidence and future attack risk. It uses forecasting attack graphs rather than our proposed pipeline.

The companion [A foresight model for intrusion response management](https://www.sciencedirect.com/science/article/pii/S0167404816300700), DOI 10.1016/j.cose.2016.06.005, explicitly considers potential attack probabilities when estimating response costs. Its indexed publisher preview was inspected; full methods remain unverified.

### 11. Attack plan recognition using hidden Markov and probabilistic inference — Li et al., 2020

[Publisher preview](https://www.sciencedirect.com/science/article/abs/pii/S0167404820302479). DOI: 10.1016/j.cose.2020.101974.

**Access:** Indexed publisher abstract/introduction/contributions; direct page blocked. An HMM attack model is converted to a BN for probabilistic reasoning with loopy belief propagation, including attack-intent prediction. This is a particularly close precedent for temporal plus Bayesian attack reasoning. Its model interface differs from our proposed likelihood emission. Do not infer absence of other features from the preview.

### 12. Early-Stage Detection of Cyber Attacks — Pivarníková, Sokol, Bajtoš, 2020

[Publisher article](https://www.mdpi.com/2078-2489/11/12/560). DOI: 10.3390/info11120560.

**Access:** Indexed publisher body, including Section 4.1; direct retrieval unsuccessful. Redundant alerts are aggregated by time, alert type, and addresses before causal relationship discovery and BN attack-stage prediction. This is a direct precedent for aggregation plus Bayesian prediction. Aggregation retains counts, so it does not establish our proposed exact-replay invariance.

### 13. Probabilistic state estimation for labeled continuous time Markov models with applications to attack detection — Lefebvre et al., 2022

[Institutional record](https://iris.unica.it/handle/11584/345189) and [author manuscript](https://www.alessandro-giua.it/UNICA/PAPERS/JOUR/22deds_up_draft.pdf).

**Access:** Primary abstract/indexed manuscript introduction; direct manuscript retrieval unsuccessful. State probabilities evolve with time using observations and their timestamps, including observable/unobservable events and attack-state subsets. This is explicit timed probabilistic cyber-state estimation. The complete method and its forecasting/response scope were not verified.

### 14. PARD-SSM: Probabilistic Cyber-Attack Regime Detection via Variational Switching State-Space Models — Hiremath et al., April 2026 preprint

[Full arXiv HTML](https://arxiv.org/html/2604.02299v1).

**Access:** Full HTML available; temporal model, predictive mechanism, and evaluation sections inspected. The authors project regime probabilities and report warnings before attack onset. Section 9.5 describes smoothed posteriors, which warrants checking whether claimed online warning results use future observations. Its reported gains are author claims, not independently reproduced results. This affects comparability, not the existence of prior predictive work.

### 15. Simulation-Informed Bayesian Stackelberg Defense for Multi-Stage Cyber Attacks — Shen, He, Zhang, 20 August 2026

[Publisher article](https://www.mdpi.com/2073-431X/15/8/545). DOI: 10.3390/computers15080545.

**Access:** Substantial indexed publisher body, including methods/evaluation descriptions; direct page/PDF retrieval blocked. Monte Carlo type-conditioned action likelihoods inform sequential Bayesian belief updates and game-theoretic defenses. Costs, partial observations, and modeled response latency are evaluated. This is functional prediction/decision overlap; it does not establish calibrated time-to-onset forecasts. The simulation method did not outperform its reference-likelihood comparator economically under the reported assumptions.

### 16. ProSpaCT: Decision-Oriented Calibrated Risk Forecasting on Evolving Cyber-Physical Systems — Kang et al., posted 8 September 2026, SSRN preprint

[Primary SSRN record](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=7435044). DOI: 10.2139/ssrn.7435044.

**Access:** Indexed primary abstract/metadata; direct full-paper retrieval unsuccessful. A spatiotemporal graph transformer incorporates calibration and predictive intervals; the abstract connects forecasts with intervention costs and audit workloads. It challenges a generic calibrated-forecast/decision novelty claim. Its exact endpoint, horizons, causal evaluation, and duplicate handling remain unverified. Treat it as a preprint, not confirmed peer-reviewed evidence.

## What remains worth investigating

### Additional combination comparisons, 4 October 2026

The [component experiment and published-result comparison](../experiments/combination_comparison/REPORT.md) adds conventional HMM, no-filter BN-observation, and temporal supervised baselines. The chosen BN-HMM construction equals a standard factorized categorical HMM to numerical precision. Syllabus-model names alone therefore do not identify a distinct inference algorithm.

Three additional precedents were checked: [Ingale et al., 2020, HMM + Naive Bayes](https://ieeexplore.ieee.org/document/9155895), whose primary title was verified but full method/results were unavailable; [Zhang et al., 2022, pre-trained HMM](https://www.mdpi.com/1424-8220/22/8/2874), whose indexed author article describes stage detection on attack-only alert sequences; and [AlertBERT, February 2026 preprint](https://arxiv.org/html/2602.06534v1), whose full methods/evaluation and [author code](https://github.com/ait-aecid/AlertBERT) were inspected. AlertBERT groups alerts on AIT-derived augmented data and reports clustering metrics, so its scores cannot be compared directly to our onset forecasts. Its reported embedding readout uses padding on both ends; causal adaptation needs explicit checking. None of these complete systems was reproduced here, and no superiority claim is established.

The original association research question was narrower than the architecture:

> How does uncertainty about whether alerts describe the same underlying event affect pre-onset forecast calibration and defensive decisions, and can a specified evidence-dependency treatment improve that tradeoff beyond ordinary deduplication and standard temporal Bayesian inference?

This is a candidate question, not a verified original method. The current proposal mostly uses established solutions: deterministic grouping, conventional likelihood filtering, standard first-arrival calculations, calibration, and expected utility. Merely relabeling these as “evidence-aware” would not establish a new mechanism.

A stronger study would distinguish exact report replays, repeated genuine actions, multiple sensors observing one action, independent corroboration, and uncertain matches. Report invariance should apply to replayed records of a single observation, not to real attack repetition or additional independent evidence. Specify any new probabilistic association/dependency model and compare it with established alert-fusion and temporal-model alternatives. Search probabilistic data association and dependent sensor fusion before calling that mechanism original.

Preserve the syllabus coverage: Unit 1 BN evidence inference; Unit 2 HMM temporal inference; Unit 3 Decision Network response selection. Syllabus coverage is a design constraint, not a research contribution.

## Evidence required before a paper claim

1. Remove phase-label-derived features and dataset-specific shortcuts; use evidence available before the forecast timestamp.
2. Define the endpoint as first DDoS launch or another independently annotated harmful outcome. Detecting an ongoing precursor attack is distinct from forecasting the terminal outcome.
3. Use independent campaigns and benign exposure, with separate training, calibration, and test runs. Two DARPA scenarios cannot establish generalization by treating their many alert rows as independent attacks.
4. Compare BN-only, HMM-only, coherent BN-HMM, ordinary deduplication plus the same pipeline, a strong direct forecasting baseline, and relevant published methods where reproducible. Match information and tuning budgets.
5. Measure warning recall at a fixed false-warning budget, lead time, horizon Brier/calibration, and response costs. Test duplicates and timing changes at identical clock timestamps, preserving the underlying episode.
6. Show which component causes improvement through ablations and campaign-level uncertainty. Passive replay can support forecast quality and modeled decision utility; demonstrated attack prevention requires measured action effects.
7. Resolve the closest incomplete full-text comparisons before submission. Recheck newly released literature against the final implemented contribution.

The exploratory duplicate replay performed during project inspection illustrates report-count sensitivity in the current implementation. It does not demonstrate that a proposed correction improves forecasting or response performance.

## Correction to the earlier proposal

The design document previously said the 2026 Stackelberg paper connects **calibrated forecasts** to decisions. The inspected material supports simulated likelihoods, confidence-weighted Bayesian updates, and response selection; calibration of first-onset probabilities was not established. That statement has been narrowed in the design document.

The earlier candidate novelty should therefore be read as a research hypothesis. The current description is: **an implemented integration of established probabilistic methods with exploratory warning/calibration tradeoffs against standard baselines**. The expanded evaluation provides reproducible empirical findings; originality and superiority to published full systems still require further evidence.

## Additional checks for the implemented duration/fusion study

- **Holgado, Villagrá and Vázquez, Real-Time Multistep Attack Prediction Based on Hidden Markov Models**, TDSC 17(1), 134–147 (2020 issue; online publication 2017), DOI 10.1109/TDSC.2017.2751478. The [authors’ institutional indexed record](https://portalcientifico.upm.es/en/ipublic/item/5643464) verifies multistep HMM prediction from IDS alerts and a CVE-based observation mapping. Full method text and author code were not obtained; search results without accessible primary methods do not count as a reproduced comparator.
- **Tan and Xi, Hidden semi-Markov model for anomaly detection**, Applied Mathematics and Computation 205(2), 562–567 (2008), DOI 10.1016/j.amc.2008.05.028. The [indexed publisher abstract and introduction](https://www.sciencedirect.com/science/article/pii/S0096300308003342) explicitly describe HSMM intrusion anomaly detection motivated by duration limitations of HMMs, using system-call sequences. The [author’s institutional page](https://iat.ustc.edu.cn/iat/x223/20210523/4751.html) independently lists the paper. This establishes prior cybersecurity use of duration models, not an identical first-onset task; full text remains unavailable.
- **Dass, Datta and Siami Namin, Attack Prediction using Hidden Markov Model**, COMPSAC 2021; [original paper](https://arxiv.org/abs/2106.02012). Full PDF inspected. It uses HMM/Viterbi attack-family prediction with an action-spoofing case study. Its outcome and reported evaluation do not reproduce our horizon/false-warning protocol, so direct accuracy comparison would be invalid.
- The [official scikit-learn stacking documentation](https://scikit-learn.org/stable/modules/generated/sklearn.ensemble.StackingClassifier.html) describes training a final estimator on cross-validated base outputs. Our campaign-based inner prediction/logistic CPD applies that established principle. It is not a first-ever probabilistic fusion method.

The [extended empirical report](../experiments/extended_study/REPORT.md) preserves
all comparisons. The fixed feature ablations also show that the three-sensor
temporal tree improves 15-minute warning coverage from 2/8 for AMiner alone to
5/8 at three false episodes for each, with 30.3% lower mean Brier. At five
minutes AMiner alone has better ranking and coverage than the full tree/fusion.
This supports a horizon-dependent empirical contribution, not universal gains
or original model principles. A fresh independent test and compatible published
full-system reproductions remain the decisive missing evidence.

## Additional primary-source checks and implemented adaptations

| Source | Verified scope | Treatment in this project |
|---|---|---|
| [Perera Miriya Thanthrige, Samarabandu and Wang (2016)](https://arxiv.org/html/1610.07276), *Intrusion Alert Prediction Using a Hidden Markov Model* | Full manuscript available: alert bag of words, k-means clusters, Baum-Welch HMM, last Viterbi state, next-cluster projection; DARPA experiments | Implemented fixed 10-cluster/8-state adaptation to minute-count features. Added target-onset hazard and filtered-state comparator. Original next-alert accuracy is not a comparable first-onset score. |
| [Ansari, Bartoš and Lee (2022)](https://research.tus.ie/en/publications/gru-based-deep-learning-approach-for-network-intrusion-alert-pred/), DOI 10.1016/j.future.2021.09.040 | Author-uploaded full manuscript now inspected: next Warden alert tuples, 512-unit GRU, up to 500 epochs with early stopping; institutional PDF retrieval remains blocked | Implemented a bounded three-layer GRU inspired by the model family, with a documented new clock-count representation and first-onset output. No exact author-code reproduction or claim of optimized GRU performance. |
| [Tijjani et al., arXiv:2601.06734v2](https://arxiv.org/abs/2601.06734) | Withdrawn on 1 April 2026 because significant analysis errors affect conclusions | Exclude its reported high accuracy from validated performance comparisons; withdrawal does not establish our originality. |
| [Landauer et al., CAM-LDS](https://zenodo.org/records/18390561), [author scripts](https://github.com/ait-aecid/attack-manifestations-interpretation) | Full scenario logs, execution annotations and separately attack-filtered manifestations | Retrieve full Wazuh streams and execution logs for six fixed distinct templates. Three contain an explicit privilege-escalation tactic. Frozen AIT transfer produces no warning at 15 minutes; missing AMiner (Suricata is present through Wazuh) and scant pre-outcome exposure prevent a full-pipeline validation claim. |
| [Landauer et al., Maintainable Log Datasets](https://arxiv.org/pdf/2203.08580.pdf), Section 3.2/Table 4 | DNS exfiltration is intentionally separate and starts at simulation beginning; privilege escalation is login as a system user, followed by root command execution | Resolves the earlier ordering concern without modifying published labels. Treat change-user and first successful root session as distinct outcomes. |

The reproduced numerical comparison is between our implementations on one
common task. It is not proof that these papers' complete methods perform worse.
The paper should contribute an endpoint-audited benchmark and conditional alarm
tradeoffs. Claiming the pipeline is unused in all literature remains unsupported.

## Additional author-code and stronger-comparator check

The [completed comparison report](../experiments/published_comparison/REPORT.md)
records eight additional GRU fits, validation-only checkpoint selection and
four alarm budgets for 15 model variants. Longer training raises GRU AP, and
its five-minute AP exceeds both our full tree and fusion, while its Brier is
worse. At 30 minutes and a tighter validation budget, fusion gives fewer timely
warnings than the tree at the same test false-episode count. No all-metric or
all-policy superiority is supported.

The [PARD-SSM author repository](https://github.com/prakulhiremath/PARD-in-Network-Traffic-using-Switching-State-Space-Models-)
was located and 11 limited files were downloaded at pinned commit
`ae7fb258f4795d704d8fc4fb76eb253522bd5753`, retaining its Apache-2.0 license.
Unmodified author filter probabilities pass a causal-prefix check. The reviewed
standard experiment fits preprocessing separately on test, uses the first
window and evaluates retrospective Viterbi states. Its fit updates transition
and initial probabilities, leaving regime A/C/Q/R unchanged. This available
path does not reproduce the paper's complete predictive/KL alert evaluation
or our first-onset task. These are source-comparison limitations, not evidence
that the paper's full system performs worse. See `author_source_audit.json`.

[GeoGuard-PTI](https://www.frontiersin.org/journals/artificial-intelligence/articles/10.3389/frai.2026.1850560/full)
is a peer-reviewed June 2026 predictive-threat paper combining geo-temporal
graph learning, propagation forecasts and simulated adaptive defense. Its
datasets are augmented with synthetic geographic propagation. The public
availability statement links the generic Kaggle catalog rather than a matched
processed-trace/implementation package; compatible reproduction was not
established. Its forecast accuracy and simulated prevention figures cannot
rank our different campaign-onset endpoint. It supplies further prior art for
broad predictive-warning and decision claims.

## Completed availability and state-feature revision

The subsequent [selective fusion round](../experiments/selective_fusion/REPORT.md)
uses established campaign-held-out fitting, sigmoid calibration and convex
weights by horizon and sensor subset. All six variants were fixed before
the new scores. Its full-input adaptive 15-minute target fails. A prespecified
fixed .25 blend improves 30-minute coverage/Brier versus original counts,
with a false-episode gain dominated by wheeler; without that case the gain
reverses. Selective fusion with Wazuh absent improves coverage/Brier/AP versus
matched pooled counts, while increasing negative warning duration. These are
limited exploratory empirical findings, not verified architectural originality
or complete published-system superiority. All 33 tests pass and independent
checks reconstruct nested fitting exclusions, weights, calibrators and scores.

The [revised experiment](../experiments/robust_forecasting/REPORT.md) tests
availability-specific counts experts, inner campaign-cross-fitted BN/HMM
posterior features, a validation-selected blend, temporal context controls and
a separately selected alarm-confirmation branch. These are integrations of
established methods, not a verified previously unpublished architecture.
The first protocol predates the completed revised scores; the confirmation
protocol follows observed forecast deterioration. All test campaigns were
already inspected and all failed variants are retained.

At 15 minutes, removing Wazuh changes old zero-warning behavior to 3/8 timely
warnings with one false episode for the availability-specific counts expert.
The useful change belongs to input availability and its fitting/selection
policy. Without AMiner, BN/HMM features recover 2/8 versus 0/8 for the matching
counts baseline, accompanied by 13 rather than 3 false episodes. Full-input
state augmentation worsens 15-minute coverage and probability error. At 30
minutes it lowers false episodes but increases probability error. The tested
probability-preserving alarm branch selects no HMM confirmation at 15 or 30
minutes across every availability subset and tested alarm budget. It therefore
does not show additional HMM value at those horizons. These results support
conditional empirical findings and negative ablations, not an unqualified
claim that the BN/HMM/Decision Network combination gives better early warnings.

All three syllabus units have substantive implementations in the augmented
candidate. Actual tree-split audits confirm state-feature use; computation
alone is not an empirical contribution. Complete published-system superiority,
architectural priority, independent generalization and physical prevention
remain unestablished. The older literature/source limits above still apply.

The full author-uploaded Ansari manuscript is now accessible through
[the author's manuscript page](https://www.researchgate.net/publication/355133237_GRU-based_deep_learning_approach_for_network_intrusion_alert_prediction).
It uses next Warden alert tuples and a substantially larger/longer-trained
configuration. Our bounded GRUs are explicit task adaptations, not complete
paper reproductions.
