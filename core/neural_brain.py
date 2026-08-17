"""
core/neural_brain.py — Neural Network Brain & Self-Learning Engine for MJ-AI
=============================================================================
A deep learning evaluation brain implemented in NumPy that featurizes Python code,
predicts code execution risk, performs real-time online backpropagation learning,
and prevents dangerous or broken self-modifications.
"""

import os
import sys
import ast
import json
import time
from pathlib import Path
from typing import Tuple, Dict, Any, Optional
import numpy as np


def get_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent


BASE_DIR = get_base_dir()
MEMORY_DIR = BASE_DIR / "memory"
WEIGHTS_PATH = MEMORY_DIR / "neural_weights.npz"
HISTORY_PATH = MEMORY_DIR / "neural_history.json"

# Number of features extracted from code
NUM_FEATURES = 10


class NeuralBrain:
    """
    Continuous Online Learning Neural Network that evaluates code safety,
    predicts modification risk, and learns from execution outcomes.
    """

    def __init__(self, lr: float = 0.02):
        self.lr = lr
        self.iterations = 0
        self.history = []

        # Architecture: 10 Features -> Dense(10, 16) -> ReLU -> Dense(16, 8) -> ReLU -> Dense(8, 1) -> Sigmoid
        # Initialize Weights (He Initialization)
        self.w1 = np.random.randn(NUM_FEATURES, 16) * np.sqrt(2.0 / NUM_FEATURES)
        self.b1 = np.zeros((1, 16))

        self.w2 = np.random.randn(16, 8) * np.sqrt(2.0 / 16)
        self.b2 = np.zeros((1, 8))

        self.w3 = np.random.randn(8, 1) * np.sqrt(2.0 / 8)
        self.b3 = np.zeros((1, 1))

        # Adam optimizer state
        self.m_w1, self.v_w1 = np.zeros_like(self.w1), np.zeros_like(self.w1)
        self.m_b1, self.v_b1 = np.zeros_like(self.b1), np.zeros_like(self.b1)
        self.m_w2, self.v_w2 = np.zeros_like(self.w2), np.zeros_like(self.w2)
        self.m_b2, self.v_b2 = np.zeros_like(self.b2), np.zeros_like(self.b2)
        self.m_w3, self.v_w3 = np.zeros_like(self.w3), np.zeros_like(self.w3)
        self.m_b3, self.v_b3 = np.zeros_like(self.b3), np.zeros_like(self.b3)

        # Feature normalization state
        self.feature_means = np.zeros((1, NUM_FEATURES))
        self.feature_stds = np.ones((1, NUM_FEATURES))

        # Load persisted weights if available
        self.load_weights()

    def _extract_code_features(self, code_str: str, file_path: str = "") -> np.ndarray:
        """
        Extract 10 structural & safety features from Python code string.
        """
        lines = code_str.splitlines()
        total_lines = len(lines)
        code_length = len(code_str)

        try:
            tree = ast.parse(code_str)
            syntax_valid = 1.0
            num_functions = sum(isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) for n in ast.walk(tree))
            num_classes = sum(isinstance(n, ast.ClassDef) for n in ast.walk(tree))
            num_try_except = sum(isinstance(n, ast.Try) for n in ast.walk(tree))
            num_loops = sum(isinstance(n, (ast.For, ast.While, ast.AsyncFor)) for n in ast.walk(tree))
        except Exception:
            syntax_valid = 0.0
            num_functions = 0
            num_classes = 0
            num_try_except = 0
            num_loops = 0

        # Dangerous patterns check (eval, exec, rm -rf, os.system dangerous calls)
        dangerous_patterns = ["eval(", "exec(", "rm -rf", "shutil.rmtree('/')", "sys.exit("]
        danger_count = sum(code_str.count(p) for p in dangerous_patterns)

        # Import safety
        import_count = code_str.count("import ") + code_str.count("from ")

        # Target file sensitivity (main.py, config vs peripheral actions)
        is_core_file = 1.0 if any(core in file_path.lower() for core in ["main.py", "core/", "config/"]) else 0.0

        features = np.array([[
            float(total_lines) / 100.0,       # 0: Normalized line count
            float(code_length) / 5000.0,      # 1: Normalized length
            float(syntax_valid),              # 2: AST syntax validity (1.0 = valid, 0.0 = invalid)
            float(num_functions) / 10.0,      # 3: Functions count
            float(num_classes) / 5.0,         # 4: Classes count
            float(num_try_except) / 5.0,      # 5: Try-catch safety blocks
            float(num_loops) / 10.0,          # 6: Loops count
            float(danger_count),              # 7: Danger pattern count
            float(import_count) / 10.0,       # 8: Imports count
            float(is_core_file),              # 9: File criticality
        ]], dtype=np.float64)

        return features

    def _sigmoid(self, z: np.ndarray) -> np.ndarray:
        return 1.0 / (1.0 + np.exp(-np.clip(z, -500.0, 500.0)))

    def _relu(self, z: np.ndarray) -> np.ndarray:
        return np.maximum(0.0, z)

    def forward(self, X: np.ndarray) -> Tuple[np.ndarray, Dict[str, np.ndarray]]:
        """Forward pass through neural network."""
        # Layer 1
        z1 = np.dot(X, self.w1) + self.b1
        a1 = self._relu(z1)

        # Layer 2
        z2 = np.dot(a1, self.w2) + self.b2
        a2 = self._relu(z2)

        # Layer 3 (Output: Probability of Success in [0, 1])
        z3 = np.dot(a2, self.w3) + self.b3
        a3 = self._sigmoid(z3)

        cache = {"X": X, "z1": z1, "a1": a1, "z2": z2, "a2": a2, "z3": z3, "a3": a3}
        return a3, cache

    def predict_success_probability(self, code_str: str, file_path: str = "") -> float:
        """Predicts probability (0.0 to 1.0) that the code modification will succeed cleanly."""
        X = self._extract_code_features(code_str, file_path)
        prob, _ = self.forward(X)
        return float(prob[0, 0])

    def predict_risk(self, code_str: str, file_path: str = "") -> float:
        """Predicts risk score (0.0 = safe, 1.0 = high risk)."""
        success_prob = self.predict_success_probability(code_str, file_path)
        return float(1.0 - success_prob)

    def learn_outcome(self, code_str: str, file_path: str, success: bool, error_msg: str = ""):
        """
        Executes online backpropagation gradient descent based on execution outcome.
        :param success: True if code modification compiled & ran without error, False otherwise.
        """
        X = self._extract_code_features(code_str, file_path)
        y_true = np.array([[1.0 if success else 0.0]], dtype=np.float64)

        # Forward pass
        y_pred, cache = self.forward(X)
        eps = 1e-15
        y_pred_clipped = np.clip(y_pred, eps, 1.0 - eps)
        loss = -float(y_true * np.log(y_pred_clipped) + (1.0 - y_true) * np.log(1.0 - y_pred_clipped))

        # Backward pass (Analytical gradients)
        # dL/dz3 = y_pred - y_true
        dz3 = y_pred - y_true
        dw3 = np.dot(cache["a2"].T, dz3)
        db3 = np.sum(dz3, axis=0, keepdims=True)

        da2 = np.dot(dz3, self.w3.T)
        dz2 = da2 * (cache["z2"] > 0.0)
        dw2 = np.dot(cache["a1"].T, dz2)
        db2 = np.sum(dz2, axis=0, keepdims=True)

        da1 = np.dot(dz2, self.w2.T)
        dz1 = da1 * (cache["z1"] > 0.0)
        dw1 = np.dot(cache["X"].T, dz1)
        db1 = np.sum(dz1, axis=0, keepdims=True)

        # Adam Parameter Updates
        self.iterations += 1
        t = self.iterations
        beta1, beta2, eps_adam = 0.9, 0.999, 1e-8
        bc1 = 1.0 - (beta1 ** t)
        bc2 = 1.0 - (beta2 ** t)
        step = self.lr * np.sqrt(bc2) / bc1

        for w, dw, mw, vw in [
            (self.w1, dw1, self.m_w1, self.v_w1),
            (self.w2, dw2, self.m_w2, self.v_w2),
            (self.w3, dw3, self.m_w3, self.v_w3),
        ]:
            mw[:] = beta1 * mw + (1.0 - beta1) * dw
            vw[:] = beta2 * vw + (1.0 - beta2) * (dw ** 2)
            w -= step * (mw / (np.sqrt(vw) + eps_adam * np.sqrt(bc2)))

        for b, db, mb, vb in [
            (self.b1, db1, self.m_b1, self.v_b1),
            (self.b2, db2, self.m_b2, self.v_b2),
            (self.b3, db3, self.m_b3, self.v_b3),
        ]:
            mb[:] = beta1 * mb + (1.0 - beta1) * db
            vb[:] = beta2 * vb + (1.0 - beta2) * (db ** 2)
            b -= step * (mb / (np.sqrt(vb) + eps_adam * np.sqrt(bc2)))

        # Record learning event
        event = {
            "timestamp": time.time(),
            "target": file_path,
            "success": success,
            "loss": loss,
            "pred_before": float(y_pred[0, 0]),
            "error_msg": error_msg[:200] if error_msg else None,
        }
        self.history.append(event)
        if len(self.history) > 100:
            self.history = self.history[-100:]

        # Save weights to disk
        self.save_weights()
        print(f"[NeuralBrain] 🧠 Backprop Completed. Loss: {loss:.4f} | Outcome: {'✅ Success' if success else '❌ Failure'}")

    def save_weights(self):
        """Persist neural network weights and history."""
        MEMORY_DIR.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(
            WEIGHTS_PATH,
            w1=self.w1, b1=self.b1,
            w2=self.w2, b2=self.b2,
            w3=self.w3, b3=self.b3,
            iterations=np.array([self.iterations]),
        )
        try:
            with open(HISTORY_PATH, "w", encoding="utf-8") as f:
                json.dump(self.history, f, indent=2)
        except Exception:
            pass

    def load_weights(self):
        """Load persisted weights if available."""
        if WEIGHTS_PATH.exists():
            try:
                data = np.load(WEIGHTS_PATH)
                self.w1 = data["w1"]
                self.b1 = data["b1"]
                self.w2 = data["w2"]
                self.b2 = data["b2"]
                self.w3 = data["w3"]
                self.b3 = data["b3"]
                if "iterations" in data:
                    self.iterations = int(data["iterations"][0])
                print(f"[NeuralBrain] ⚡ Restored neural weights ({self.iterations} prior learning steps).")
            except Exception as e:
                print(f"[NeuralBrain] Notice: Initializing fresh neural weights: {e}")

    def get_status(self) -> Dict[str, Any]:
        """Return diagnostic status of the Neural Brain."""
        recent_acc = 1.0
        if self.history:
            correct = sum(
                1 for h in self.history if (h["pred_before"] >= 0.5 and h["success"]) or (h["pred_before"] < 0.5 and not h["success"])
            )
            recent_acc = correct / len(self.history)

        return {
            "total_learning_steps": self.iterations,
            "total_events_logged": len(self.history),
            "recent_prediction_accuracy": f"{recent_acc * 100:.1f}%",
            "weights_file": str(WEIGHTS_PATH),
            "status": "Online & Learning",
        }


# Global singleton instance
_brain_instance: Optional[NeuralBrain] = None


def get_neural_brain() -> NeuralBrain:
    global _brain_instance
    if _brain_instance is None:
        _brain_instance = NeuralBrain()
    return _brain_instance
