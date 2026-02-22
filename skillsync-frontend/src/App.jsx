import React, { useState, useRef, useEffect } from 'react';
import Editor from '@monaco-editor/react';
import {
  Upload, FileText, Activity, ShieldCheck, Link, Loader2, Code, Lightbulb,
  Target, Zap, Play, CheckCircle, RefreshCw, ArrowRight, Brain, Terminal, Send
} from 'lucide-react';
import { Radar, RadarChart, PolarGrid, PolarAngleAxis, ResponsiveContainer } from 'recharts';

const App = () => {
  // View Mode: 'home' | 'coding' | 'results'
  const [viewMode, setViewMode] = useState('home');

  // Document Analysis State
  const [file, setFile] = useState(null);
  const [urlInput, setUrlInput] = useState("");
  const [analysis, setAnalysis] = useState(null);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [error, setError] = useState(null);

  // 🎯 BATCH ASSESSMENT STATE (Always 4 questions)
  const [batchQuestions, setBatchQuestions] = useState([]); // Array of 4 questions
  const [currentQuestionIndex, setCurrentQuestionIndex] = useState(0); // 0-3
  const [questionResults, setQuestionResults] = useState({}); // Track results per question

  // Coding IDE State
  const editorRef = useRef(null);
  const [output, setOutput] = useState("Click 'Run Code' to test with sample cases, or 'Submit' for full evaluation...");
  const [isRunning, setIsRunning] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isEvaluating, setIsEvaluating] = useState(false);

  // Per-question persistent state (survives question switching)
  // Each array is indexed by question index (0-3)
  const [perQuestionCode, setPerQuestionCode] = useState([]);       // user's edited code per question
  const [perQuestionOutput, setPerQuestionOutput] = useState([]);   // terminal output per question
  const [perQuestionRunCount, setPerQuestionRunCount] = useState([]); // run attempts per question
  const [perQuestionLogs, setPerQuestionLogs] = useState([]);       // error logs per question

  // 🔥 DUAL TESTING: sampleTests for "Run Code", comprehensiveTests for "Submit"
  const [scenario, setScenario] = useState({
    title: "Scenario: N-ary Tree Properties",
    description: `## Problem Statement
Given the root of an N-ary tree, count its leaf nodes, internal nodes, and find the maximum number of children any node has.

A **leaf node** is a node with no children.
An **internal node** is a node with at least one child.

## Examples
**Example 1:**
Input: root = [1, [2, [5, 6]], 3, [4, [7]]]
Output: [4, 3, 3]
Explanation: Leaf nodes: 5, 6, 3, 7 (count=4). Internal nodes: 1, 2, 4 (count=3). Max children: node 1 has 3 children.

**Example 2:**
Input: root = [10, [20, 30]]
Output: [2, 1, 2]

**Example 3:**
Input: root = [50]
Output: [1, 0, 0]

## Constraints
- The number of nodes is in the range [1, 10^4]
- 0 <= Node.data <= 10^5`,
    userCode: `from typing import List, Optional, Dict, Set, Tuple

class Node:
    def __init__(self, data: int = 0):
        self.data = data
        self.children: List['Node'] = []

class Solution:
    def countTreeProperties(self, root: 'Node') -> List[int]:
        """
        Count leaf nodes, internal nodes, and max children in an N-ary tree.
        
        Args:
            root: The root node of the N-ary tree
            
        Returns:
            A list of three integers: [num_leaf_nodes, num_internal_nodes, max_children_count]
        """
        pass`,
    sampleTests: `import sys
from typing import List, Optional, Dict, Set, Tuple

class Node:
    def __init__(self, data: int = 0):
        self.data = data
        self.children: List['Node'] = []

if __name__ == '__main__':
    solution = Solution()
    passed = 0
    total = 3

    # --- Sample Test 1 ---
    n1 = Node(1); n2 = Node(2); n3 = Node(3); n4 = Node(4)
    n5 = Node(5); n6 = Node(6); n7 = Node(7)
    n1.children = [n2, n3, n4]
    n2.children = [n5, n6]
    n4.children = [n7]
    
    expected1 = [4, 3, 3]
    try:
        actual1 = solution.countTreeProperties(n1)
    except Exception as e:
        actual1 = f"ERROR: {e}"
    
    print("--- Sample Test 1 ---")
    print(f"Input: root = [1, [2, [5, 6]], 3, [4, [7]]]")
    print(f"Expected: {expected1}")
    print(f"Actual: {actual1}")
    if actual1 == expected1:
        print("Status: PASS")
        passed += 1
    else:
        print("Status: FAIL")
    print()

    # --- Sample Test 2 ---
    n10 = Node(10); n20 = Node(20); n30 = Node(30)
    n10.children = [n20, n30]
    expected2 = [2, 1, 2]
    try:
        actual2 = solution.countTreeProperties(n10)
    except Exception as e:
        actual2 = f"ERROR: {e}"
    
    print("--- Sample Test 2 ---")
    print(f"Input: root = [10, [20, 30]]")
    print(f"Expected: {expected2}")
    print(f"Actual: {actual2}")
    if actual2 == expected2:
        print("Status: PASS")
        passed += 1
    else:
        print("Status: FAIL")
    print()

    # --- Sample Test 3 ---
    n50 = Node(50)
    expected3 = [1, 0, 0]
    try:
        actual3 = solution.countTreeProperties(n50)
    except Exception as e:
        actual3 = f"ERROR: {e}"
    
    print("--- Sample Test 3 ---")
    print(f"Input: root = [50]")
    print(f"Expected: {expected3}")
    print(f"Actual: {actual3}")
    if actual3 == expected3:
        print("Status: PASS")
        passed += 1
    else:
        print("Status: FAIL")
    print()

    print("=" * 30)
    print(f"Sample Tests: {passed}/{total} Passed")
    print("=" * 30)`,
    comprehensiveTests: `import sys
from typing import List, Optional, Dict, Set, Tuple

# ===== DATA STRUCTURE DEFINITION =====
class Node:
    def __init__(self, data: int = 0):
        self.data = data
        self.children: List['Node'] = []

# ===== HELPER FUNCTION: Build tree from nested list =====
def build_tree(data):
    """
    Build N-ary tree from nested list format.
    Format: [val, [child1_data], [child2_data], ...]
    Example: [1, [2, [5], [6]], [3], [4, [7]]]
    """
    if not data:
        return None
    root = Node(data[0])
    for child_data in data[1:]:
        child = build_tree(child_data)
        if child:
            root.children.append(child)
    return root

# ===== REFERENCE SOLUTION: Compute expected values =====
def compute_expected(root):
    """Reference implementation to compute [leaf_count, internal_count, max_children]."""
    if not root:
        return [0, 0, 0]
    leaf_count = 0
    internal_count = 0
    max_children = 0
    
    def dfs(node):
        nonlocal leaf_count, internal_count, max_children
        max_children = max(max_children, len(node.children))
        if not node.children:
            leaf_count += 1
        else:
            internal_count += 1
            for child in node.children:
                dfs(child)
    
    dfs(root)
    return [leaf_count, internal_count, max_children]

# ===== TEST EXECUTION =====
if __name__ == '__main__':
    solution = Solution()
    
    # ===== TEST DATA: Simple Python lists only! =====
    test_data = [
        # Basic cases from problem examples
        [1, [2, [5], [6]], [3], [4, [7]]],      # Example 1: [4, 3, 3]
        [10, [20], [30]],                        # Example 2: [2, 1, 2]
        [50],                                    # Example 3: Single node [1, 0, 0]
        
        # Edge cases
        [1, [2, [3, [4, [5]]]]],                 # Linear chain depth 5: [1, 4, 1]
        [0, [1], [2], [3], [4], [5], [6], [7], [8], [9], [10]],  # Wide: 10 children
        [1, [2, [4], [5]], [3, [6], [7]]],      # Balanced binary-like
        [100],                                   # Single large value
        [1, [2]],                                # Minimal tree with 1 child
        [1, [2], [3]],                           # Root with 2 leaf children
        [1, [2, [3]], [4, [5]]],                 # Symmetric depth 2
    ]
    
    # Add programmatically generated cases (no variable naming issues!)
    for i in range(10, 35):
        # Generate varied tree structures using simple data
        tree_data = [i]
        num_children = (i % 5) + 1
        for c in range(num_children):
            child_data = [i * 10 + c]
            num_grandchildren = i % 3
            for g in range(num_grandchildren):
                child_data.append([i * 100 + c * 10 + g])
            tree_data.append(child_data)
        test_data.append(tree_data)
    
    # Build test cases with computed expected values
    test_cases = []
    for data in test_data:
        root = build_tree(data)
        expected = compute_expected(root)
        test_cases.append((data, expected))
    
    # ===== TEST RUNNER =====
    total = len(test_cases)
    for i, (input_data, expected) in enumerate(test_cases):
        root = build_tree(input_data)
        try:
            actual = solution.countTreeProperties(root)
        except Exception as e:
            print(f"Runtime Error: {i} / {total} testcases passed")
            print()
            print(f"Input:")
            print(f"{input_data}")
            print()
            print(f"Error Message: {e}")
            sys.exit(1)
        
        if actual != expected:
            print(f"Wrong Answer: {i} / {total} testcases passed")
            print()
            print(f"Input:")
            print(f"{input_data}")
            print()
            print(f"Output:")
            print(f"{actual}")
            print()
            print(f"Expected:")
            print(f"{expected}")
            sys.exit(0)
    
    print(f"Accepted: {total}/{total} testcases passed")
    print("All test cases passed!")`
  });

  // Telemetry Trackers (The "Struggle" Data)
  const [runCount, setRunCount] = useState(0);
  const [sessionLogs, setSessionLogs] = useState([]);

  // 🛡️ ANTI-CHEAT TELEMETRY (tab switches + paste events)
  const [tabSwitchCount, setTabSwitchCount] = useState(0);
  const [pasteCount, setPasteCount] = useState(0);
  const tabSwitchRef = useRef(0);
  const pasteRef = useRef(0);

  // Track tab switches via Page Visibility API
  useEffect(() => {
    const handleVisibilityChange = () => {
      if (document.hidden && viewMode === 'coding') {
        tabSwitchRef.current += 1;
        setTabSwitchCount(tabSwitchRef.current);
        console.warn(`[ANTI-CHEAT] Tab switch #${tabSwitchRef.current} detected`);
      }
    };
    document.addEventListener('visibilitychange', handleVisibilityChange);
    return () => document.removeEventListener('visibilitychange', handleVisibilityChange);
  }, [viewMode]);

  // Track paste events in the editor area
  useEffect(() => {
    const handlePaste = (e) => {
      if (viewMode === 'coding') {
        const pastedText = e.clipboardData?.getData('text') || '';
        // Only count meaningful pastes (>20 chars = likely code, not a variable name)
        if (pastedText.length > 20) {
          pasteRef.current += 1;
          setPasteCount(pasteRef.current);
          console.warn(`[ANTI-CHEAT] Code paste #${pasteRef.current} detected (${pastedText.length} chars)`);
        }
      }
    };
    document.addEventListener('paste', handlePaste);
    return () => document.removeEventListener('paste', handlePaste);
  }, [viewMode]);

  // Results State
  const [results, setResults] = useState(null);

  // ============================================
  // DOCUMENT ANALYSIS HANDLERS
  // ============================================

  const handleFileUpload = async (e) => {
    const selectedFile = e.target.files[0];
    if (!selectedFile) return;

    setFile(selectedFile);
    setIsAnalyzing(true);
    setError(null);
    setAnalysis(null);

    const formData = new FormData();
    formData.append("file", selectedFile);

    try {
      const response = await fetch("http://localhost:8000/analyze-doc", {
        method: "POST",
        body: formData,
      });

      if (!response.ok) throw new Error(`Analysis failed: ${response.statusText}`);

      const data = await response.json();

      // Check if this is a fallback response
      if (data.is_fallback) {
        console.warn("⚠️ Received fallback response - Gemini API may have failed");
        setError("AI service temporarily unavailable. Showing default challenge. Please try again.");
      }

      setAnalysis(data);

      // 🔥 DUAL TESTING: Store both test suites
      if (data.user_code) {
        setScenario({
          title: `Scenario: ${data.category}`,
          description: data.summary,
          userCode: data.user_code,
          sampleTests: data.sample_tests || "",
          comprehensiveTests: data.comprehensive_tests || ""
        });
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setIsAnalyzing(false);
    }
  };

  const handleUrlAnalysis = async () => {
    if (!urlInput.trim()) return;

    setIsAnalyzing(true);
    setError(null);
    setAnalysis(null);
    setBatchQuestions([]);

    try {
      // Generate 4-question assessment
      const response = await fetch("http://localhost:8000/analyze-url", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url: urlInput }),
      });

      if (!response.ok) throw new Error(`Analysis failed: ${response.statusText}`);

      const data = await response.json();

      // Check if this is a fallback response
      if (data.is_fallback) {
        console.warn("⚠️ Received fallback response - Gemini API may have failed");
        setError("AI service temporarily unavailable. Showing default challenge. Please try again.");
      }

      setAnalysis(data);

      // Store array of 4 questions
      if (data.questions && data.questions.length > 0) {
        console.log(`Assessment loaded: ${data.questions.length} questions`);
        const questions = data.questions;
        setBatchQuestions(questions);
        setCurrentQuestionIndex(0);
        setQuestionResults({});

        // Initialize per-question persistent state
        setPerQuestionCode(questions.map(q => q.user_code));
        setPerQuestionOutput(questions.map((q, i) =>
          `Question ${i + 1}/4: ${q.title}\nType: ${q.question_type.toUpperCase()}\n\nClick 'Run Code' to test...`
        ));
        setPerQuestionRunCount(questions.map(() => 0));
        setPerQuestionLogs(questions.map(() => []));

        // Set the first question (scratch) as the active scenario
        const firstQuestion = questions[0];
        setScenario({
          title: firstQuestion.title,
          description: firstQuestion.description,
          userCode: firstQuestion.user_code,
          sampleTests: firstQuestion.sample_tests || "",
          comprehensiveTests: firstQuestion.comprehensive_tests || ""
        });
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setIsAnalyzing(false);
    }
  };

  const startCodingChallenge = () => {
    setViewMode('coding');
    setResults(null);

    // Start with question 0 (scratch type)
    if (batchQuestions.length > 0) {
      setCurrentQuestionIndex(0);
      // Load saved state for question 0
      setOutput(perQuestionOutput[0] || "Click 'Run Code' to test with sample cases, or 'Submit' for full evaluation...");
      setRunCount(perQuestionRunCount[0] || 0);
      setSessionLogs(perQuestionLogs[0] || []);

      const question = batchQuestions[0];
      setScenario({
        title: question.title,
        description: question.description,
        userCode: perQuestionCode[0] || question.user_code,
        sampleTests: question.sample_tests || "",
        comprehensiveTests: question.comprehensive_tests || ""
      });
    } else {
      setOutput("Click 'Run Code' to test with sample cases, or 'Submit' for full evaluation...");
      setRunCount(0);
      setSessionLogs([]);
    }
  };

  // Helper: save the current question's live state into the per-question arrays
  const saveCurrentQuestionState = () => {
    const idx = currentQuestionIndex;
    if (idx < 0 || idx >= batchQuestions.length) return;

    // Save editor content (the most important one — prevents code loss)
    const currentCode = editorRef.current ? editorRef.current.getValue() : perQuestionCode[idx];
    setPerQuestionCode(prev => { const copy = [...prev]; copy[idx] = currentCode; return copy; });

    // Save terminal output
    setPerQuestionOutput(prev => { const copy = [...prev]; copy[idx] = output; return copy; });

    // Save run count and error logs
    setPerQuestionRunCount(prev => { const copy = [...prev]; copy[idx] = runCount; return copy; });
    setPerQuestionLogs(prev => { const copy = [...prev]; copy[idx] = sessionLogs; return copy; });
  };

  // BATCH MODE: Load a specific question by index (saves current first)
  const loadQuestion = (index) => {
    if (index < 0 || index >= batchQuestions.length) return;
    if (index === currentQuestionIndex) return; // already on this question

    // 1. Save current question's state
    saveCurrentQuestionState();

    // 2. Switch to target question
    const question = batchQuestions[index];
    setCurrentQuestionIndex(index);

    // 3. Restore target question's scenario (description, tests)
    const savedCode = perQuestionCode[index] || question.user_code;
    setScenario({
      title: question.title,
      description: question.description,
      userCode: savedCode,
      sampleTests: question.sample_tests || "",
      comprehensiveTests: question.comprehensive_tests || ""
    });

    // 4. Restore target question's editor content
    if (editorRef.current) {
      editorRef.current.setValue(savedCode);
    }

    // 5. Restore target question's terminal output, run count, logs
    setOutput(perQuestionOutput[index] || `Question ${index + 1}/4: ${question.title}\nType: ${question.question_type.toUpperCase()}\n\nClick 'Run Code' to test...`);
    setRunCount(perQuestionRunCount[index] || 0);
    setSessionLogs(perQuestionLogs[index] || []);
  };

  // Navigate to next question (saves current state automatically via loadQuestion)
  const goToNextQuestion = () => {
    if (currentQuestionIndex < batchQuestions.length - 1) {
      loadQuestion(currentQuestionIndex + 1);
    }
  };

  // Navigate to previous question (saves current state automatically via loadQuestion)
  const goToPreviousQuestion = () => {
    if (currentQuestionIndex > 0) {
      loadQuestion(currentQuestionIndex - 1);
    }
  };

  // 🎯 Get question type badge color
  const getQuestionTypeBadge = (type) => {
    const badges = {
      scratch: { bg: "bg-blue-500/20", text: "text-blue-400", label: "Scratch" },
      logic_bug: { bg: "bg-red-500/20", text: "text-red-400", label: "🐛 Logic Bug" },
      syntax_error: { bg: "bg-yellow-500/20", text: "text-yellow-400", label: "🔧 Syntax Fix" },
      optimization: { bg: "bg-purple-500/20", text: "text-purple-400", label: "⚡ Optimize" }
    };
    return badges[type] || { bg: "bg-slate-500/20", text: "text-slate-400", label: type };
  };

  // ============================================
  // CODING IDE HANDLERS
  // ============================================

  const handleEditorMount = (editor) => {
    editorRef.current = editor;
  };

  // RUN CODE: Uses sample_tests (3 basic test cases)
  const handleRunCode = async () => {
    setIsRunning(true);
    setOutput("Running sample tests...");
    const userCode = editorRef.current.getValue();
    const currentAttempt = runCount + 1;
    setRunCount(currentAttempt);

    // Persist code into per-question state immediately
    const idx = currentQuestionIndex;
    setPerQuestionCode(prev => { const copy = [...prev]; copy[idx] = userCode; return copy; });
    setPerQuestionRunCount(prev => { const copy = [...prev]; copy[idx] = currentAttempt; return copy; });

    try {
      const response = await fetch("http://localhost:8000/execute", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          code: userCode,
          sample_tests: scenario.sampleTests,
          comprehensive_tests: scenario.comprehensiveTests,
          is_submit: false  // Run Code mode
        }),
      });
      const data = await response.json();

      let resultText = "";
      if (data.stderr && data.stderr.trim()) {
        resultText = `ERRORS:\n${data.stderr}\n\n`;
      }
      if (data.stdout && data.stdout.trim()) {
        resultText += data.stdout;
      }
      if (!resultText.trim()) {
        resultText = "No output. Make sure your solution returns a value.";
      }
      setOutput(resultText);
      setPerQuestionOutput(prev => { const copy = [...prev]; copy[idx] = resultText; return copy; });

      // Track errors from BOTH stderr AND stdout failure patterns
      const hasStderrError = data.stderr && data.stderr.trim();
      const stdoutText = data.stdout || '';
      const hasStdoutFailure = /FAIL|Wrong Answer|Runtime Error|Error Message:/.test(stdoutText);

      if (hasStderrError || hasStdoutFailure) {
        const errorContent = hasStderrError
          ? data.stderr
          : stdoutText.split('\n').filter(l => /FAIL|Wrong Answer|Runtime Error|Error/.test(l)).join('\n');
        const newLog = { attempt: currentAttempt, log: errorContent };
        setSessionLogs(prev => {
          const updated = [...prev, newLog];
          setPerQuestionLogs(prevLogs => { const copy = [...prevLogs]; copy[idx] = updated; return copy; });
          return updated;
        });
      }
    } catch (err) {
      const errMsg = "Error: Could not connect to execution engine.";
      setOutput(errMsg);
      setPerQuestionOutput(prev => { const copy = [...prev]; copy[idx] = errMsg; return copy; });
    } finally {
      setIsRunning(false);
    }
  };

  // SUBMIT: Uses comprehensive_tests (50+ edge cases)
  const handleSubmitCode = async () => {
    setIsSubmitting(true);
    setOutput("Running comprehensive tests (50+ cases)...");
    const userCode = editorRef.current.getValue();
    const currentAttempt = runCount + 1;
    setRunCount(currentAttempt);

    // Persist code into per-question state immediately
    const idx = currentQuestionIndex;
    setPerQuestionCode(prev => { const copy = [...prev]; copy[idx] = userCode; return copy; });
    setPerQuestionRunCount(prev => { const copy = [...prev]; copy[idx] = currentAttempt; return copy; });

    try {
      const response = await fetch("http://localhost:8000/execute", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          code: userCode,
          sample_tests: scenario.sampleTests,
          comprehensive_tests: scenario.comprehensiveTests,
          is_submit: true  // Submit mode - use comprehensive tests
        }),
      });
      const data = await response.json();

      let resultText = "";
      if (data.stderr && data.stderr.trim()) {
        resultText = `ERRORS:\n${data.stderr}\n\n`;
      }
      if (data.stdout && data.stdout.trim()) {
        resultText += data.stdout;
      }
      if (!resultText.trim()) {
        resultText = "No output. Make sure your solution returns a value.";
      }
      setOutput(resultText);
      setPerQuestionOutput(prev => { const copy = [...prev]; copy[idx] = resultText; return copy; });

      // Track errors from BOTH stderr AND stdout failure patterns
      const hasStderrError = data.stderr && data.stderr.trim();
      const stdoutText = data.stdout || '';
      const hasStdoutFailure = /FAIL|Wrong Answer|Runtime Error|Error Message:/.test(stdoutText);

      if (hasStderrError || hasStdoutFailure) {
        const errorContent = hasStderrError
          ? data.stderr
          : stdoutText.split('\n').filter(l => /FAIL|Wrong Answer|Runtime Error|Error/.test(l)).join('\n');
        const newLog = { attempt: currentAttempt, log: errorContent };
        setSessionLogs(prev => {
          const updated = [...prev, newLog];
          setPerQuestionLogs(prevLogs => { const copy = [...prevLogs]; copy[idx] = updated; return copy; });
          return updated;
        });
      }
    } catch (err) {
      const errMsg = "Error: Could not connect to execution engine.";
      setOutput(errMsg);
      setPerQuestionOutput(prev => { const copy = [...prev]; copy[idx] = errMsg; return copy; });
    } finally {
      setIsSubmitting(false);
    }
  };

  // EVALUATE: Send ALL 4 questions' telemetry to AI for holistic cognitive profiling
  const handleEvaluate = async () => {
    setIsEvaluating(true);

    // Save the current question's live state first
    saveCurrentQuestionState();

    // Snapshot the latest editor code for the active question
    const latestCode = editorRef.current ? editorRef.current.getValue() : perQuestionCode[currentQuestionIndex];
    const codeSnapshot = [...perQuestionCode];
    codeSnapshot[currentQuestionIndex] = latestCode;

    const runCountSnapshot = [...perQuestionRunCount];
    runCountSnapshot[currentQuestionIndex] = runCount;

    const logsSnapshot = [...perQuestionLogs];
    logsSnapshot[currentQuestionIndex] = sessionLogs;

    // Build batch payload with telemetry for ALL questions
    if (batchQuestions.length > 0) {
      // BATCH MODE: Send all 4 questions
      const batchPayload = {
        questions: batchQuestions.map((q, idx) => ({
          question_type: q.question_type,
          title: q.title,
          code: codeSnapshot[idx] || q.user_code,
          attempts: runCountSnapshot[idx] || 0,
          logs: (logsSnapshot[idx] || []).map((log, logIdx) => ({
            attempt: log.attempt || logIdx + 1,
            log: log.log || ""
          }))
        })),
        tab_switches: tabSwitchRef.current,
        paste_count: pasteRef.current,
      };

      console.log("Sending batch evaluation:", batchPayload.questions.map(q =>
        `${q.question_type}: ${q.attempts} attempts, ${q.logs.length} errors, ${q.code.length} chars`
      ));

      try {
        const response = await fetch("http://localhost:8000/batch-submit", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(batchPayload),
        });
        const data = await response.json();
        setResults(data);
        setViewMode('results');
      } catch (err) {
        alert("Error: Could not connect to AI Proctor.");
      } finally {
        setIsEvaluating(false);
      }
    } else {
      // SINGLE QUESTION FALLBACK (demo mode / non-batch)
      const finalPayload = {
        code: latestCode,
        attempts: runCount,
        logs: sessionLogs,
        tab_switches: tabSwitchRef.current,
        paste_count: pasteRef.current,
      };

      try {
        const response = await fetch("http://localhost:8000/submit", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(finalPayload),
        });
        const data = await response.json();
        setResults(data);
        setViewMode('results');
      } catch (err) {
        alert("Error: Could not connect to AI Proctor.");
      } finally {
        setIsEvaluating(false);
      }
    }
  };

  const resetAll = () => {
    setViewMode('home');
    setAnalysis(null);
    setFile(null);
    setUrlInput("");
    setError(null);
    setResults(null);
    setRunCount(0);
    setSessionLogs([]);
    setBatchQuestions([]);
    setCurrentQuestionIndex(0);
    setQuestionResults({});
    setPerQuestionCode([]);
    setPerQuestionOutput([]);
    setPerQuestionRunCount([]);
    setPerQuestionLogs([]);
  };

  // ============================================
  // RENDER: RESULTS VIEW (Radar Chart)
  // ============================================

  if (viewMode === 'results' && results) {
    const chartData = [
      { subject: 'Logic', A: results.logic_score, fullMark: 100 },
      { subject: 'Resilience', A: results.resilience_score, fullMark: 100 },
      { subject: 'Clean Code', A: results.clean_code_score, fullMark: 100 },
      { subject: 'Debugging', A: results.debugging_score, fullMark: 100 },
      { subject: 'Originality', A: results.originality_score, fullMark: 100 },
    ];

    return (
      <div className="min-h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 text-white p-10 flex items-center justify-center">
        <div className="max-w-4xl w-full bg-slate-800/50 backdrop-blur rounded-2xl p-8 border border-slate-700">
          <div className="flex justify-between items-center mb-8">
            <div>
              <h1 className="text-3xl font-bold bg-gradient-to-r from-blue-400 to-purple-400 bg-clip-text text-transparent">
                Cognitive Profile Generated
              </h1>
              <p className="text-slate-400 mt-1">AI-powered skill assessment complete</p>
            </div>
            <button onClick={resetAll} className="flex items-center gap-2 text-slate-400 hover:text-white transition px-4 py-2 rounded-lg border border-slate-600 hover:border-slate-500">
              <RefreshCw size={18} /> New Session
            </button>
          </div>

          <div className="flex flex-col md:flex-row gap-8">
            <div className="w-full md:w-1/2 h-72 bg-slate-900/50 rounded-xl p-4 border border-slate-700">
              <ResponsiveContainer width="100%" height="100%">
                <RadarChart cx="50%" cy="50%" outerRadius="80%" data={chartData}>
                  <PolarGrid stroke="#374151" />
                  <PolarAngleAxis dataKey="subject" tick={{ fill: '#9CA3AF', fontSize: 12 }} />
                  <Radar name="Candidate" dataKey="A" stroke="#3B82F6" strokeWidth={2} fill="#3B82F6" fillOpacity={0.5} />
                </RadarChart>
              </ResponsiveContainer>
            </div>

            <div className="w-full md:w-1/2 flex flex-col justify-center space-y-4">
              <div className="bg-slate-900/50 p-5 rounded-xl border border-slate-700">
                <h3 className="text-sm text-slate-500 uppercase font-bold tracking-wider mb-2">Executive Summary</h3>
                <p className="text-slate-300 leading-relaxed">{results.executive_summary}</p>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div className="bg-slate-900/50 p-4 rounded-xl border border-slate-700 text-center">
                  <div className="text-3xl font-bold text-green-400">{results.logic_score}</div>
                  <div className="text-xs text-slate-500 uppercase mt-1">Logic Score</div>
                </div>
                <div className="bg-slate-900/50 p-4 rounded-xl border border-slate-700 text-center">
                  <div className="text-3xl font-bold text-purple-400">{results.resilience_score}</div>
                  <div className="text-xs text-slate-500 uppercase mt-1">Grit Metric</div>
                </div>
                <div className="bg-slate-900/50 p-4 rounded-xl border border-slate-700 text-center">
                  <div className="text-3xl font-bold text-blue-400">{results.clean_code_score}</div>
                  <div className="text-xs text-slate-500 uppercase mt-1">Clean Code</div>
                </div>
                <div className="bg-slate-900/50 p-4 rounded-xl border border-slate-700 text-center">
                  <div className="text-3xl font-bold text-yellow-400">{results.debugging_score}</div>
                  <div className="text-xs text-slate-500 uppercase mt-1">Debugging</div>
                </div>
                <div className={`col-span-2 p-4 rounded-xl border text-center ${(results.originality_score) < 30
                  ? "bg-red-900/30 border-red-500/50"
                  : "bg-slate-900/50 border-slate-700"
                  }`}>
                  <div className={`text-3xl font-bold ${(results.originality_score) < 30 ? "text-red-400" : "text-emerald-400"
                    }`}>{results.originality_score}</div>
                  <div className="text-xs text-slate-500 uppercase mt-1">
                    Originality {(results.originality_score) < 30 && "— Flagged"}
                  </div>
                </div>
              </div>
            </div>
          </div>

          <div className="mt-6 p-4 bg-slate-900/30 rounded-xl border border-slate-700">
            <p className="text-sm text-slate-500">
              <span className="font-semibold text-slate-400">Session Telemetry:</span>{' '}
              {perQuestionRunCount.reduce((a, b) => a + b, 0) || runCount} total execution attempts,{' '}
              {perQuestionLogs.reduce((a, b) => a + b.length, 0) || sessionLogs.length} total errors,{' '}
              {batchQuestions.length || 1} question(s) evaluated
              {tabSwitchCount > 0 && (
                <span className={tabSwitchCount >= 5 ? "text-red-400 font-semibold" : "text-yellow-400"}>
                  {' '}| 🔀 {tabSwitchCount} tab switch{tabSwitchCount !== 1 ? 'es' : ''}
                </span>
              )}
              {pasteCount > 0 && (
                <span className="text-red-400 font-semibold">
                  {' '}| 📋 {pasteCount} paste{pasteCount !== 1 ? 's' : ''} detected
                </span>
              )}
            </p>
          </div>
        </div>
      </div>
    );
  }

  // ============================================
  // RENDER: CODING IDE VIEW
  // ============================================

  if (viewMode === 'coding') {
    const currentQuestion = batchQuestions.length > 0
      ? batchQuestions[currentQuestionIndex]
      : null;
    const questionBadge = currentQuestion ? getQuestionTypeBadge(currentQuestion.question_type) : null;

    return (
      <div className="flex h-screen bg-slate-900 text-white">
        {/* Left Panel - Problem Description */}
        <div className="w-2/5 p-6 border-r border-slate-700 flex flex-col bg-slate-800/30 overflow-hidden">
          <div className="flex items-center gap-3 mb-4">
            <div className="bg-gradient-to-r from-blue-500 to-purple-600 p-2 rounded-lg">
              <Brain size={20} />
            </div>
            <h1 className="text-xl font-bold">SkillSync</h1>
          </div>

          {/* 🎯 Question Navigation */}
          {batchQuestions.length > 0 && (
            <div className="mb-4 p-3 bg-slate-900/50 rounded-xl border border-slate-700">
              <div className="flex items-center justify-between mb-3">
                <span className="text-sm font-semibold text-slate-400">
                  Question {currentQuestionIndex + 1} of {batchQuestions.length}
                </span>
                {questionBadge && (
                  <span className={`text-xs font-bold px-2 py-1 rounded ${questionBadge.bg} ${questionBadge.text}`}>
                    {questionBadge.label}
                  </span>
                )}
              </div>

              {/* Question Type Tabs */}
              <div className="grid grid-cols-4 gap-1">
                {batchQuestions.map((q, idx) => {
                  const badge = getQuestionTypeBadge(q.question_type);
                  return (
                    <button
                      key={idx}
                      onClick={() => loadQuestion(idx)}
                      className={`p-2 rounded-lg text-xs font-medium transition-all ${idx === currentQuestionIndex
                        ? `${badge.bg} ${badge.text} border border-current`
                        : "bg-slate-800 text-slate-500 hover:bg-slate-700"
                        }`}
                    >
                      {idx + 1}
                    </button>
                  );
                })}
              </div>

              {/* Prev/Next Buttons */}
              <div className="flex gap-2 mt-3">
                <button
                  onClick={goToPreviousQuestion}
                  disabled={currentQuestionIndex === 0}
                  className="flex-1 py-2 px-3 rounded-lg text-sm font-medium bg-slate-800 hover:bg-slate-700 disabled:opacity-50 disabled:cursor-not-allowed transition"
                >
                  ← Previous
                </button>
                <button
                  onClick={goToNextQuestion}
                  disabled={currentQuestionIndex === batchQuestions.length - 1}
                  className="flex-1 py-2 px-3 rounded-lg text-sm font-medium bg-slate-800 hover:bg-slate-700 disabled:opacity-50 disabled:cursor-not-allowed transition"
                >
                  Next →
                </button>
              </div>
            </div>
          )}

          {/* Problem Description */}
          <div className="bg-slate-800/50 p-5 rounded-xl border border-slate-700 flex-grow overflow-y-auto">
            <h2 className="text-lg font-semibold text-blue-400 mb-4">{scenario.title}</h2>

            <div className="prose prose-invert prose-sm max-w-none">
              <div className="text-slate-300 text-sm leading-relaxed space-y-3">
                {scenario.description.split('\n').map((line, i) => {
                  if (line.startsWith('## ')) {
                    return <h3 key={i} className="text-blue-400 font-semibold text-base mt-4 mb-2">{line.replace('## ', '')}</h3>;
                  } else if (line.startsWith('**') && line.endsWith('**')) {
                    return <p key={i} className="font-semibold text-white">{line.replace(/\*\*/g, '')}</p>;
                  } else if (line.startsWith('- ')) {
                    return <p key={i} className="text-slate-400 pl-4">• {line.replace('- ', '')}</p>;
                  } else if (line.startsWith('Input:') || line.startsWith('Output:') || line.startsWith('Explanation:')) {
                    const [label, ...rest] = line.split(':');
                    return (
                      <p key={i} className="font-mono text-sm">
                        <span className="text-purple-400">{label}:</span>
                        <span className="text-green-300">{rest.join(':')}</span>
                      </p>
                    );
                  } else if (line.trim()) {
                    return <p key={i} className="text-slate-300">{line}</p>;
                  }
                  return null;
                })}
              </div>
            </div>
          </div>

          {/* Live Telemetry */}
          <div className="mt-4 pt-4 border-t border-slate-700">
            <h3 className="text-xs text-slate-500 uppercase tracking-wider mb-2">Live Telemetry</h3>
            <div className="grid grid-cols-2 gap-3">
              <div className="bg-slate-900/50 p-3 rounded-lg text-center">
                <div className="text-2xl font-bold text-yellow-400">{runCount}</div>
                <div className="text-xs text-slate-500">Runs (this Q)</div>
              </div>
              <div className="bg-slate-900/50 p-3 rounded-lg text-center">
                <div className="text-2xl font-bold text-red-400">{sessionLogs.length}</div>
                <div className="text-xs text-slate-500">Errors (this Q)</div>
              </div>
            </div>
            {batchQuestions.length > 1 && (
              <div className="mt-2 text-xs text-slate-600 text-center">
                Total: {perQuestionRunCount.reduce((a, b) => a + b, 0)} runs, {perQuestionLogs.reduce((a, b) => a + b.length, 0)} errors across all questions
              </div>
            )}
          </div>

          <button onClick={resetAll} className="mt-4 text-sm text-slate-500 hover:text-slate-300 transition">
            ← Back to Home
          </button>
        </div>

        {/* Right Panel - Code Editor */}
        <div className="w-3/5 flex flex-col">
          <div className="flex justify-between items-center p-3 bg-slate-800 border-b border-slate-700">
            <div className="flex items-center gap-2">
              <Terminal size={16} className="text-slate-400" />
              <span className="text-sm text-slate-400">solution.py</span>
            </div>
            <div className="flex gap-2">
              {/* Run Code Button - Sample Tests */}
              <button
                onClick={handleRunCode}
                disabled={isRunning || isSubmitting}
                className={`px-4 py-2 rounded-lg flex items-center text-sm transition ${isRunning ? 'bg-slate-700 text-slate-400' : 'bg-slate-700 hover:bg-slate-600 text-white'
                  }`}
              >
                <Play size={16} className={`mr-2 ${isRunning ? 'text-slate-400' : 'text-green-400'}`} />
                {isRunning ? 'Running...' : 'Run Code'}
              </button>

              {/* Submit Button - Comprehensive Tests */}
              <button
                onClick={handleSubmitCode}
                disabled={isRunning || isSubmitting}
                className={`px-4 py-2 rounded-lg flex items-center text-sm font-semibold transition ${isSubmitting ? 'bg-green-800' : 'bg-green-600 hover:bg-green-500 text-white'
                  }`}
              >
                <Send size={16} className="mr-2" />
                {isSubmitting ? 'Judging...' : 'Submit'}
              </button>

              {/* AI Evaluate Button */}
              <button
                onClick={handleEvaluate}
                disabled={isEvaluating}
                className={`px-4 py-2 rounded-lg flex items-center text-sm font-semibold transition ${isEvaluating ? 'bg-purple-800' : 'bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-500 hover:to-purple-500'
                  }`}
              >
                <CheckCircle size={16} className="mr-2" />
                {isEvaluating ? 'Analyzing...' : 'AI Evaluate'}
              </button>
            </div>
          </div>

          <div className="flex-grow">
            <Editor
              height="100%"
              defaultLanguage="python"
              theme="vs-dark"
              key={`editor-q${currentQuestionIndex}`}
              defaultValue={scenario.userCode}
              onMount={handleEditorMount}
              options={{ minimap: { enabled: false }, fontSize: 14, padding: { top: 16 } }}
            />
          </div>

          {/* Terminal Output */}
          <div className="h-52 bg-black border-t border-slate-700 p-4 overflow-y-auto">
            <div className="text-xs text-slate-500 mb-2 uppercase tracking-wider font-bold flex items-center gap-2">
              <Terminal size={12} /> Test Results
            </div>
            <pre className="text-sm font-mono whitespace-pre-wrap">
              {output.split('\n').map((line, i) => {
                if (line.startsWith('--- Sample Test') || line.startsWith('--- Test')) {
                  return <div key={i} className="text-blue-400 font-bold mt-2">{line}</div>;
                } else if (line.startsWith('Input:')) {
                  return <div key={i} className="text-slate-400">{line}</div>;
                } else if (line.startsWith('Expected:')) {
                  return <div key={i} className="text-yellow-400">{line}</div>;
                } else if (line.startsWith('Actual:')) {
                  const hasError = line.includes('ERROR') || line.includes('None');
                  return <div key={i} className={hasError ? "text-red-400" : "text-cyan-400"}>{line}</div>;
                } else if (line.includes('Status: PASS') || line.includes('PASS')) {
                  return <div key={i} className="text-green-400 font-semibold">{line}</div>;
                } else if (line.includes('Status: FAIL') || line.includes('FAIL') || line.includes('Wrong Answer')) {
                  return <div key={i} className="text-red-400 font-semibold">{line}</div>;
                } else if (line.includes('Accepted:') || line.includes('All test cases passed')) {
                  return <div key={i} className="text-green-400 font-bold text-base mt-2">{line}</div>;
                } else if (line.includes('Sample Tests:') || line.includes('Passed')) {
                  return <div key={i} className="text-yellow-400 font-bold">{line}</div>;
                } else if (line.startsWith('=')) {
                  return <div key={i} className="text-slate-600">{line}</div>;
                } else if (line.includes('ERROR') || line.includes('Runtime Error') || line.includes('Error:')) {
                  return <div key={i} className="text-red-400">{line}</div>;
                }
                return <div key={i} className="text-slate-300">{line}</div>;
              })}
            </pre>
          </div>
        </div>
      </div>
    );
  }

  // ============================================
  // RENDER: HOME VIEW (Document Analysis)
  // ============================================

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 text-white p-8">
      <div className="max-w-6xl mx-auto">
        {/* Navigation */}
        <nav className="flex justify-between items-center mb-12">
          <h1 className="text-2xl font-bold flex items-center gap-3">
            <div className="bg-gradient-to-r from-blue-500 to-purple-600 p-2 rounded-lg">
              <Activity size={24} />
            </div>
            <span className="bg-gradient-to-r from-blue-400 to-purple-400 bg-clip-text text-transparent">
              SkillSync
            </span>
            <span className="text-slate-500 text-sm font-normal ml-2">Cognitive Evaluation Engine</span>
          </h1>
          <div className="flex gap-6 text-sm font-medium text-slate-400">
            <span className="hover:text-white cursor-pointer transition">Docs</span>
            <span className="hover:text-white cursor-pointer transition">API</span>
            <span className="text-blue-400 hover:text-blue-300 cursor-pointer transition">Enterprise</span>
          </div>
        </nav>

        {/* Hero Section */}
        {!analysis && !isAnalyzing && (
          <div className="text-center mb-12">
            <h2 className="text-4xl font-bold mb-4">
              Generate AI-Powered Skill Assessments
            </h2>
            <p className="text-slate-400 text-lg max-w-2xl mx-auto">
              Upload any technical document or paste a URL. Our AI extracts concepts and generates
              bespoke coding challenges that measure real cognitive skills.
            </p>
          </div>
        )}

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          {/* Upload Section */}
          <div className="lg:col-span-1 space-y-6">
            <div className="bg-slate-800/50 backdrop-blur p-6 rounded-2xl border border-slate-700">
              <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
                <Zap className="text-yellow-400" size={20} />
                Ingest Study Material
              </h2>

              {/* File Upload */}
              <label className="border-2 border-dashed border-slate-600 rounded-xl p-8 flex flex-col items-center cursor-pointer hover:border-blue-500 hover:bg-slate-700/30 transition-all group">
                <Upload className="text-slate-400 mb-3 group-hover:text-blue-400 transition" size={32} />
                <span className="text-sm text-slate-400 text-center group-hover:text-slate-300">
                  Upload PDF or Text File
                </span>
                <span className="text-xs text-slate-500 mt-1">Textbooks, articles, docs</span>
                <input
                  type="file"
                  className="hidden"
                  onChange={handleFileUpload}
                  accept=".pdf,.txt,.json,.md"
                  disabled={isAnalyzing}
                />
              </label>

              {/* Divider */}
              <div className="flex items-center gap-4 my-6">
                <div className="flex-1 h-px bg-slate-700"></div>
                <span className="text-xs text-slate-500 uppercase tracking-wider">or</span>
                <div className="flex-1 h-px bg-slate-700"></div>
              </div>

              {/* URL Input */}
              <div className="space-y-3">
                <div className="flex bg-slate-900 rounded-lg border border-slate-700 overflow-hidden">
                  <div className="px-3 flex items-center bg-slate-800 border-r border-slate-700">
                    <Link size={16} className="text-slate-400" />
                  </div>
                  <input
                    type="text"
                    placeholder="Paste GeeksForGeeks URL..."
                    className="flex-1 bg-transparent text-sm text-white px-3 py-3 outline-none placeholder:text-slate-500"
                    value={urlInput}
                    onChange={(e) => setUrlInput(e.target.value)}
                    disabled={isAnalyzing}
                  />
                </div>

                {/* Info about what will be generated */}
                <p className="text-xs text-slate-500 text-center">
                  Generates 4 challenge types: Scratch • Debug • Syntax Fix • Optimization
                </p>

                <button
                  onClick={handleUrlAnalysis}
                  disabled={isAnalyzing || !urlInput.trim()}
                  className="w-full bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-500 hover:to-purple-500 text-white py-3 rounded-lg text-sm font-semibold transition-all disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {isAnalyzing ? "Generating 4 Challenges..." : "Generate Assessment"}
                </button>
              </div>
            </div>

            {/* Quick Start */}
            <button
              onClick={startCodingChallenge}
              className="w-full bg-slate-800/50 hover:bg-slate-700/50 p-4 rounded-xl border border-slate-700 hover:border-blue-500 transition flex items-center justify-between group"
            >
              <div className="flex items-center gap-3">
                <Code className="text-green-400" size={20} />
                <span className="font-medium">Try Demo Challenge</span>
              </div>
              <ArrowRight className="text-slate-500 group-hover:text-white transition" size={18} />
            </button>
          </div>

          {/* Results Section */}
          <div className="lg:col-span-2">
            {isAnalyzing ? (
              <div className="bg-slate-800/50 backdrop-blur p-16 rounded-2xl border border-slate-700 flex flex-col items-center justify-center">
                <Loader2 className="animate-spin text-blue-400 mb-4" size={48} />
                <p className="text-lg font-medium">Processing Document...</p>
                <p className="text-sm text-slate-400 mt-2">AI is generating sample + comprehensive test suites</p>
              </div>
            ) : error ? (
              <div className="bg-red-900/20 border border-red-500/50 p-8 rounded-2xl text-center">
                <p className="text-red-400 font-medium">Analysis Failed</p>
                <p className="text-sm text-red-300/70 mt-2">{error}</p>
                <button onClick={() => setError(null)} className="mt-4 text-sm text-red-400 hover:text-red-300 underline">
                  Try Again
                </button>
              </div>
            ) : analysis ? (
              <div className="space-y-6">
                {/* Header Card */}
                <div className="bg-slate-800/50 backdrop-blur p-8 rounded-2xl border border-slate-700 border-t-4 border-t-purple-500">
                  <div className="flex justify-between items-start mb-6">
                    <div>
                      <span className="bg-purple-500/20 text-purple-400 text-xs font-bold px-3 py-1 rounded-full uppercase tracking-wider">
                        📚 {analysis.topic || "Assessment"}
                      </span>
                      <h2 className="text-2xl font-bold mt-3">
                        {batchQuestions.length} Questions Generated
                      </h2>
                    </div>
                    <div className="flex items-center gap-2 bg-green-500/20 px-3 py-2 rounded-lg">
                      <ShieldCheck className="text-green-400" size={20} />
                      <span className="text-green-400 text-sm font-medium">
                        {analysis.estimated_time_minutes || 45} min
                      </span>
                    </div>
                  </div>

                  {/* Questions Preview */}
                  {batchQuestions.length > 0 && (
                    <div className="space-y-3 mt-6">
                      <h3 className="text-sm font-semibold text-slate-400 uppercase tracking-wider">Challenge Types</h3>
                      <div className="grid grid-cols-2 gap-3">
                        {batchQuestions.map((q, idx) => {
                          const badge = getQuestionTypeBadge(q.question_type);
                          return (
                            <div
                              key={idx}
                              className="p-4 rounded-xl border bg-slate-900/50 border-slate-700 hover:border-slate-500 transition-all"
                            >
                              <div className="flex items-center gap-2 mb-2">
                                <span className={`text-xs font-bold px-2 py-0.5 rounded ${badge.bg} ${badge.text}`}>
                                  {badge.label}
                                </span>
                                <span className="text-xs text-slate-500">{q.time_limit_minutes} min</span>
                              </div>
                              <p className="font-medium text-sm truncate">{q.title}</p>
                              <p className="text-xs text-slate-500 mt-1">{q.difficulty}</p>
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  )}
                </div>

                {/* Test Suite Info */}
                <div className="bg-slate-800/50 backdrop-blur p-6 rounded-2xl border border-slate-700">
                  <h3 className="font-semibold flex items-center gap-2 mb-4">
                    <Target className="text-purple-400" size={20} />
                    Assessment Overview
                  </h3>
                  <div className="grid grid-cols-2 gap-4">
                    <div className="bg-slate-900/50 p-4 rounded-xl border border-slate-600">
                      <div className="flex items-center gap-2 mb-2">
                        <Play className="text-green-400" size={16} />
                        <span className="font-medium text-green-400">Run Code</span>
                      </div>
                      <p className="text-sm text-slate-400">3 sample test cases per question</p>
                    </div>
                    <div className="bg-slate-900/50 p-4 rounded-xl border border-slate-600">
                      <div className="flex items-center gap-2 mb-2">
                        <Send className="text-blue-400" size={16} />
                        <span className="font-medium text-blue-400">Submit</span>
                      </div>
                      <p className="text-sm text-slate-400">20+ comprehensive tests per question</p>
                    </div>
                  </div>
                </div>

                {/* Action Button */}
                <button
                  onClick={startCodingChallenge}
                  className="w-full bg-gradient-to-r from-green-600 to-blue-600 hover:from-green-500 hover:to-blue-500 text-white py-4 rounded-xl text-lg font-bold transition flex items-center justify-center gap-3"
                >
                  <Play size={24} />
                  Start Coding Challenge
                </button>
              </div>
            ) : (
              <div className="bg-slate-800/30 border-2 border-dashed border-slate-700 p-16 rounded-2xl text-center">
                <Brain className="mx-auto text-slate-600 mb-4" size={48} />
                <p className="text-slate-500 text-lg">Upload a document or paste a URL</p>
                <p className="text-slate-600 text-sm mt-2">
                  AI will generate sample tests + 50 comprehensive edge cases
                </p>
              </div>
            )}
          </div>
        </div>

        {/* Footer */}
        <footer className="mt-16 text-center text-slate-500 text-sm">
          <p>Powered by Gemini AI • Measuring Real Cognitive Skills, Not Memorization</p>
        </footer>
      </div>
    </div>
  );
};

export default App;
