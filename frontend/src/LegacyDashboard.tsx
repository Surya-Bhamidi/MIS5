import React, { useState, useEffect } from "react";
import { Header } from "./components/Header";
import { LiveFeed } from "./components/LiveFeed";
import { BeliefDistribution } from "./components/BeliefDistribution";
import { AttackGraph } from "./components/AttackGraph";
import { RecommendationCard } from "./components/RecommendationCard";
import { ExplainabilityModal } from "./components/ExplainabilityModal";
import { WhatIfSimulator } from "./components/WhatIfSimulator";
import { AblationComparison } from "./components/AblationComparison";
import { ExperimentReports } from "./components/ExperimentReports";
import { ScenarioInfo, PipelineStepResult, AblationMode, DefensiveAction } from "./types";
import { fetchScenarios, fetchPipelineBatch } from "./api/client";

export const LegacyDashboard: React.FC = () => {
  const [scenarios, setScenarios] = useState<ScenarioInfo[]>([]);
  const [selectedScenario, setSelectedScenario] = useState("events_lldos1");
  const [ablationMode, setAblationMode] = useState<AblationMode>("B3");
  const [activeTab, setActiveTab] = useState<"console" | "whatif" | "ablation" | "experiments">("console");
  const [currentIndex, setCurrentIndex] = useState(0);
  const [playRequested, setPlayRequested] = useState(false);
  const [playbackSpeed, setPlaybackSpeed] = useState(1);
  const [showProvenanceModal, setShowProvenanceModal] = useState(false);
  const [whatIfAction, setWhatIfAction] = useState<DefensiveAction>("Isolate");
  const requestKey = JSON.stringify([selectedScenario, ablationMode]);
  const [replay, setReplay] = useState<{ key: string; steps: PipelineStepResult[] } | null>(null);
  const [error, setError] = useState<{ key: string; message: string } | null>(null);
  const steps = replay?.key === requestKey ? replay.steps : [];
  const alerts = steps.map(step => step.event);
  const currentResult = steps[currentIndex] || null;
  const currentError = error?.key === requestKey ? error.message : null;
  const loading = replay?.key !== requestKey && !currentError;
  const isStreaming = playRequested && !loading && currentIndex < steps.length - 1;

  useEffect(() => {
    let active = true;
    fetchScenarios().then(result => {
      if (active) setScenarios(result.scenarios);
    }).catch(() => { if (active) setScenarios([]); });
    return () => { active = false; };
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    let active = true;
    const [scenario, mode] = JSON.parse(requestKey) as [string, AblationMode];
    fetchPipelineBatch(scenario, mode, controller.signal).then(result => {
      if (active) { setReplay({ key: requestKey, steps: result.steps }); setError(null); setCurrentIndex(0); }
    }).catch(failure => {
      if (active && failure.name !== "AbortError") setError({ key: requestKey, message: failure.message });
    });
    return () => { active = false; controller.abort(); };
  }, [requestKey]);

  useEffect(() => {
    if (!isStreaming) return;
    const timer = window.setInterval(() => setCurrentIndex(index => Math.min(index + 1, steps.length - 1)), Math.max(150, 1000 / playbackSpeed));
    return () => window.clearInterval(timer);
  }, [isStreaming, playbackSpeed, steps.length]);

  const selectIndex = (index: number) => { setPlayRequested(false); setCurrentIndex(index); };
  const placeholder = <div className="glass-card" style={{ padding: 24 }} role="status">{currentError || (loading ? "Calculating causal archived replay…" : "No archived result is available for this scenario.")}</div>;
  return <div style={{ minHeight: "100vh", display: "flex", flexDirection: "column" }}>
    <Header scenarios={scenarios} selectedScenario={selectedScenario}
      onSelectScenario={scenario => { setPlayRequested(false); setSelectedScenario(scenario); setCurrentIndex(0); }}
      ablationMode={ablationMode} onSelectAblation={mode => { setPlayRequested(false); setAblationMode(mode); setCurrentIndex(0); }}
      activeTab={activeTab} onSelectTab={tab => { setPlayRequested(false); setActiveTab(tab); }} isStreaming={isStreaming}/>
    <main style={{ maxWidth: 1600, margin: "0 auto", padding: "20px 24px 60px", width: "100%", flex: 1 }}>
      {currentError && <div role="alert">{currentError}</div>}
      {activeTab === "console" && <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
        {currentResult && <AttackGraph dominantState={currentResult.recommendation.dominant_state} viterbiPath={currentResult.viterbi_path} projections={currentResult.projections}/>}
        <div style={{ display: "grid", gridTemplateColumns: "1.45fr 1fr", gap: 20 }}>
          <LiveFeed alerts={alerts} currentIndex={currentIndex} isStreaming={isStreaming}
            onToggleStreaming={() => { if (!isStreaming && currentIndex === steps.length - 1) setCurrentIndex(0); setPlayRequested(!isStreaming); }}
            onStepForward={() => selectIndex(Math.min(currentIndex + 1, steps.length - 1))}
            onReset={() => selectIndex(0)} speed={playbackSpeed} onChangeSpeed={setPlaybackSpeed} onSelectAlert={selectIndex} loading={loading}/>
          {currentResult ? <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
            <BeliefDistribution bnBelief={currentResult.bn_belief} hmmBelief={currentResult.hmm_belief} activeBelief={currentResult.active_belief} ablationMode={ablationMode}/>
            <RecommendationCard recommendation={currentResult.recommendation} onOpenProvenance={() => setShowProvenanceModal(true)}
              onLaunchWhatIf={action => { setPlayRequested(false); setWhatIfAction(action); setActiveTab("whatif"); }} ablationMode={ablationMode}/>
          </div> : placeholder}
        </div>
      </div>}
      {activeTab === "whatif" && (currentResult ? <WhatIfSimulator currentBelief={currentResult.active_belief} initialAction={whatIfAction}/> : placeholder)}
      {activeTab === "ablation" && <AblationComparison scenarioId={selectedScenario}/>}
      {activeTab === "experiments" && <ExperimentReports/>}
    </main>
    {showProvenanceModal && currentResult && <ExplainabilityModal trace={currentResult.provenance_trace} onClose={() => setShowProvenanceModal(false)}/>}
  </div>;
};

export default LegacyDashboard;
