# MJ-X GENESIS FINAL REPORT — 03: MASTER ARCHITECTURE

**Subsystem:** Modular Intelligence & Unified System Topography  
**Architecture Paradigm:** Local-First Core, Cloud-Assisted Multimodal, Hardened Process Boundaries  

---

## 1. COMPONENT ARCHITECTURE DIAGRAM

```mermaid
graph TD
    User([User Voice & Text]) <--> UI[PyQt6 Native Desktop UI]
    UI <--> Brain[mjx.intelligence.brain.IntelligenceBrain]
    
    subgraph Intelligence Core [Project OMNIBRAIN]
        Brain --> Intent[IntentClassifier]
        Brain --> Context[ContextEngine]
        Brain --> Planner[AutonomousPlanner]
        Brain --> Decision[DecisionEngine]
        Brain --> Reflection[TaskReflectionEngine]
        Brain --> RespCtrl[ResponseController]
    end

    subgraph Security & Safety [Project P0]
        Vault[mjx.security.vault.CredentialVault]
        ProcMgr[mjx.security.process_manager.SafeProcessManager]
        Perms[mjx.security.permissions.PermissionManager]
    end

    subgraph Emotion & Prosody [Project ECHO]
        EmoEng[IntegratedEmotionEngine]
        EmoEng --> EmoDetect[ContextualEmotionDetector]
        EmoEng --> StateMgr[EmotionStateManager]
        EmoEng --> VoiceExp[VoiceExpressionController]
        EmoEng --> DynTrack[ConversationDynamicsTracker]
    end

    subgraph Memory Core [Project CORTEX / P1]
        DB[mjx.memory.database.DatabaseManager]
        Repo[mjx.memory.repository.MemoryRepository]
        FTS[SQLite FTS5 Full-Text Search]
        Norm[Hinglish Normalizer]
        Backup[Online Backup & Restore]
    end

    subgraph Desktop Agent [Project GHOST]
        AgentCtrl[DesktopAgentController]
        AgentCtrl --> Vision[DesktopPerception]
        AgentCtrl --> Guard[AgentSafetyGuard]
        AgentCtrl --> PlanGUI[DesktopActionPlanner]
        AgentCtrl --> ExecGUI[DesktopActionExecutor]
        AgentCtrl --> VerifGUI[DesktopExecutionVerifier]
    end

    subgraph Extensibility & Hub [Projects NEXUS & MIRROR]
        Skills[mjx.skills.SkillRegistry]
        MCP[mjx.skills.MCPAdapter]
        Hub[mjx.hub.VisualHubController]
    end

    subgraph Mobile Companion [Project AURORA]
        Pairing[mjx.aurora.AuroraPairingManager]
        Sync[mjx.aurora.AuroraSyncProtocol]
    end

    Planner --> Perms
    PlanGUI --> Perms
    Skills --> Perms
    ProcMgr --> Perms
    Repo --> DB
    Decision --> AgentCtrl
    Decision --> Skills
```

---

## 2. SUBSYSTEM BOUNDARIES & INTERACTION CONTRACTS

1. **Client / Server Separation:**
   - PyQt6 UI and FastAPI Dashboard communicate strictly through service abstractions and data transfer objects (DTOs).
   - Zero direct database handles exposed to presentation layers.

2. **Security Mediation:**
   - Any operation interacting with the filesystem (`FILE_WRITE`), screen (`SCREEN_CAPTURE`), camera (`CAMERA_ACCESS`), or operating system input (`OS_INPUT_CONTROL`) must obtain a lease from `PermissionManager`.

3. **Deterministic Memory Pipeline:**
   - All conversations, turns, facts, and user configurations are committed through `MemoryRepository` using SQLite WAL mode transactions with immediate rollback on exception.
