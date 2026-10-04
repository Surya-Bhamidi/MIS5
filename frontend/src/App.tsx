import React, { useState, useEffect, useRef } from "react";
import { Header } from "./components/Header";
import { LiveFeed } from "./components/LiveFeed";
import { BeliefDistribution } from "./components/BeliefDistribution";
import { AttackGraph } from "./components/AttackGraph";
import { RecommendationCard } from "./components/RecommendationCard";
import { ExplainabilityModal } from "./components/ExplainabilityModal";
import { WhatIfSimulator } from "./components/WhatIfSimulator";
import { AblationComparison } from "./components/AblationComparison";
import { ExperimentReports } from "./components/ExperimentReports";
import {
  ScenarioInfo,
  AlertEvent,
  PipelineStepResult,
  AblationMode,
  DefensiveAction,
  ThreatState,
} from "./types";
import {
  fetchScenarios,
  fetchScenarioAlerts,
  inferPipelineStep,
  resetPipeline,
} from "./api/client";

export const App: React.FC = () => {
  // Navigation & Configuration States
  const [scenarios, setScenarios] = useState<ScenarioInfo[]>([]);
  const [selectedScenario, setSelectedScenario] = useState<string>("events_lldos1");
  const [ablationMode, setAblationMode] = useState<AblationMode>("B3");
  const [activeTab, setActiveTab] = useState<"console" | "whatif" | "ablation" | "experiments">("console");

  // Streaming & Feed States
  const [alerts, setAlerts] = useState<AlertEvent[]>([]);
  const [currentIndex, setCurrentIndex] = useState<number>(0);
  const [isStreaming, setIsStreaming] = useState<boolean>(false);
  const [playbackSpeed, setPlaybackSpeed] = useState<number>(1);
  const [loading, setLoading] = useState<boolean>(false);

  // Active Pipeline State
  const [currentResult, setCurrentResult] = useState<PipelineStepResult | null>(null);
  const [showProvenanceModal, setShowProvenanceModal] = useState<boolean>(false);

  // References for streaming interval
  const isStreamingRef = useRef(isStreaming);
  isStreamingRef.current = isStreaming;
  const currentIndexRef = useRef(currentIndex);
  currentIndexRef.current = currentIndex;
  const alertsRef = useRef(alerts);
  alertsRef.current = alerts;
  const ablationModeRef = useRef(ablationMode);
  ablationModeRef.current = ablationMode;

  // 1. Initial Load of Scenarios
  useEffect(() => {
    async function init() {
      try {
        const res = await fetchScenarios();
        setScenarios(res.scenarios);
        if (res.scenarios.length > 0) {
          setSelectedScenario(res.scenarios[0].id);
        }
      } catch (err) {
        console.error("Failed to load scenarios:", err);
      }
    }
    init();
  }, []);

  // 2. Load Alerts when Scenario changes
  useEffect(() => {
    if (!selectedScenario) return;
    loadAlertsForScenario(selectedScenario);
  }, [selectedScenario]);

  const loadAlertsForScenario = async (scId: string) => {
    setIsStreaming(false);
    setLoading(true);
    try {
      await resetPipeline();
      const res = await fetchScenarioAlerts(scId, 350, 0);
      setAlerts(res.alerts);
      setCurrentIndex(0);

      // Evaluate step 0 if alerts available
      if (res.alerts.length > 0) {
        const stepOut = await inferPipelineStep(res.alerts[0], ablationMode);
        setCurrentResult(stepOut);
      } else {
        setCurrentResult(null);
      }
    } catch (err) {
      console.error("Failed to load scenario alerts:", err);
    } finally {
      setLoading(false);
    }
  };

  // 3. Process Single Step
  const processNextStep = async (nextIdx: number) => {
    if (nextIdx >= alertsRef.current.length) {
      setIsStreaming(false);
      return;
    }
    setCurrentIndex(nextIdx);
    const alert = alertsRef.current[nextIdx];
    try {
      const stepOut = await inferPipelineStep(alert, ablationModeRef.current);
      setCurrentResult(stepOut);
    } catch (err) {
      console.error("Error processing pipeline step:", err);
    }
  };

  // 4. Streaming Loop
  useEffect(() => {
    let timer: any = null;
    if (isStreaming) {
      const intervalMs = Math.max(150, 1000 / playbackSpeed);
      timer = setInterval(() => {
        if (!isStreamingRef.current) return;
        const next = currentIndexRef.current + 1;
        if (next < alertsRef.current.length) {
          processNextStep(next);
        } else {
          setIsStreaming(false);
        }
      }, intervalMs);
    }
    return () => {
      if (timer) clearInterval(timer);
    };
  }, [isStreaming, playbackSpeed]);

  const handleStepForward = () => {
    if (currentIndex < alerts.length - 1) {
      processNextStep(currentIndex + 1);
    }
  };

  const handleReset = async () => {
    setIsStreaming(false);
    setCurrentIndex(0);
    await resetPipeline();
    if (alerts.length > 0) {
      processNextStep(0);
    }
  };

  const handleSelectAlert = (index: number) => {
    setIsStreaming(false);
    processNextStep(index);
  };

  const handleLaunchWhatIf = (action: DefensiveAction) => {
    setActiveTab("whatif");
  };

  // Fallback default belief if no step evaluated yet
  const activeBelief: Record<ThreatState, number> = currentResult?.active_belief || {
    Benign: 0.85,
    Recon: 0.10,
    Discovery: 0.03,
    Compromise: 0.01,
    PrivEsc: 0.01,
    ActiveAttack: 0.00,
  };

  const bnBelief = currentResult?.bn_belief || activeBelief;
  const hmmBelief = currentResult?.hmm_belief || activeBelief;
  const dominantState = currentResult?.recommendation?.dominant_state || "Benign";
  const viterbiPath = currentResult?.viterbi_path || [dominantState];
  const projections = currentResult?.projections || [];

  return (
    <div style={{ minHeight: "100vh", display: "flex", flexDirection: "column" }}>
      {/* Top Header */}
      <Header
        scenarios={scenarios}
        selectedScenario={selectedScenario}
        onSelectScenario={setSelectedScenario}
        ablationMode={ablationMode}
        onSelectAblation={(m) => {
          setAblationMode(m);
          if (alerts.length > 0) processNextStep(currentIndex);
        }}
        activeTab={activeTab}
        onSelectTab={setActiveTab}
        isStreaming={isStreaming}
      />

      {/* Main Container */}
      <main style={{ maxWidth: "1600px", margin: "0 auto", padding: "20px 24px 60px 24px", width: "100%", flex: 1 }}>
        {/* Tab 1: Live Analyst Console */}
        {activeTab === "console" && (
          <div style={{ display: "flex", flexDirection: "column", gap: "20px" }}>
            {/* Upper Attack Graph */}
            <AttackGraph
              dominantState={dominantState}
              viterbiPath={viterbiPath}
              projections={projections}
            />

            {/* Split Grid: Feed (Left) vs Diagnostics & Recommendations (Right) */}
            <div style={{ display: "grid", gridTemplateColumns: "1.45fr 1fr", gap: "20px" }}>
              {/* Left Column: Live Feed */}
              <div>
                <LiveFeed
                  alerts={alerts}
                  currentIndex={currentIndex}
                  isStreaming={isStreaming}
                  onToggleStreaming={() => setIsStreaming(!isStreaming)}
                  onStepForward={handleStepForward}
                  onReset={handleReset}
                  speed={playbackSpeed}
                  onChangeSpeed={setPlaybackSpeed}
                  onSelectAlert={handleSelectAlert}
                  loading={loading}
                />
              </div>

              {/* Right Column: Belief Distribution + Recommendation */}
              <div style={{ display: "flex", flexDirection: "column", gap: "20px" }}>
                <BeliefDistribution
                  bnBelief={bnBelief}
                  hmmBelief={hmmBelief}
                  activeBelief={activeBelief}
                  ablationMode={ablationMode}
                />

                <RecommendationCard
                  recommendation={currentResult?.recommendation || null}
                  onOpenProvenance={() => setShowProvenanceModal(true)}
                  onLaunchWhatIf={handleLaunchWhatIf}
                  ablationMode={ablationMode}
                />
              </div>
            </div>
          </div>
        )}

        {/* Tab 2: What-If Counterfactual Simulator */}
        {activeTab === "whatif" && (
          <WhatIfSimulator currentBelief={activeBelief} />
        )}

        {/* Tab 3: Pipeline Ablation (B0 -> B3) */}
        {activeTab === "ablation" && (
          <AblationComparison scenarioId={selectedScenario} />
        )}

        {/* Tab 4: RQ1-RQ5 Empirical Evaluation Hub */}
        {activeTab === "experiments" && (
          <ExperimentReports />
        )}
      </main>

      {/* Explainability Provenance Modal */}
      {showProvenanceModal && currentResult?.provenance_trace && (
        <ExplainabilityModal
          trace={currentResult.provenance_trace}
          onClose={() => setShowProvenanceModal(false)}
        />
      )}
    </div>
  );
};

export default App;
