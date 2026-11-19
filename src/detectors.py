"""Regex-based detectors of security-relevant capabilities in agent skills.

Two families:
  * INSTRUCTION detectors run on SKILL.md text (what the skill tells the agent to do).
  * SCRIPT detectors run on bundled executable files (what the skill ships).

Each detector is a list of regular expressions; a document matches a category
when any expression matches. Patterns are deliberately conservative (favour
precision); precision is estimated by manual inspection (see validate.py).
"""
import re

F = re.IGNORECASE

INSTRUCTION = {
    # Agent is told to execute shell commands (fenced shell block or "run `cmd`").
    "shell_exec": [
        r"```(?:bash|sh|shell|zsh|console|powershell|ps1|cmd)\b",
        r"\b(?:run|execute)\s+(?:the\s+)?(?:following\s+)?(?:command|script)\b",
        r"\b(?:run|execute)\s+`[^`\n]{2,}`",
    ],
    # Agent is told to reach the network.
    "network": [
        r"\b(?:curl|wget)\s+[^\n]*https?://",
        r"\b(?:Invoke-WebRequest|iwr|Invoke-RestMethod|irm)\s+[^\n]*https?://",
        r"\brequests\.(?:get|post|put|delete)\(",
        r"\bfetch\(\s*['\"`]https?://",
        r"\b(?:git\s+clone|pip\s+install\s+git\+)\s*https?://",
    ],
    # Remote code piped straight into an interpreter.
    "remote_code_exec": [
        r"(?:curl|wget)[^\n|]{0,300}\|\s*(?:sudo\s+)?(?:ba|z|da)?sh\b",
        r"(?:curl|wget)[^\n|]{0,300}\|\s*(?:sudo\s+)?python3?\b",
        r"(?:iwr|irm|Invoke-WebRequest|Invoke-RestMethod)[^\n|]{0,300}\|\s*iex\b",
        r"\bbash\s+<\(\s*curl",
    ],
    # Destructive or history-rewriting operations.
    "destructive": [
        r"\brm\s+-(?:[a-zA-Z]*r[a-zA-Z]*f|[a-zA-Z]*f[a-zA-Z]*r)\b",
        r"\bgit\s+push\s+(?:[^\n]*\s)?(?:-f|--force)\b",
        r"\bgit\s+reset\s+--hard\b",
        r"\bgit\s+clean\s+-[a-zA-Z]*f",
        r"\bDROP\s+(?:TABLE|DATABASE)\b",
        r"\bdocker\s+system\s+prune\b",
    ],
    # Privilege escalation or weakening of permissions / agent sandbox.
    "privilege": [
        r"\bsudo\s+\S",
        r"\bchmod\s+(?:-R\s+)?777\b",
        r"--dangerously-skip-permissions\b",
        r"\bbypassPermissions\b",
        r"--no-verify\b",
    ],
    # Handling of credentials and secret material.
    "secrets": [
        r"\b(?:[A-Z0-9]+_)*(?:API_KEY|SECRET(?:_KEY)?|TOKEN|PASSWORD|PRIVATE_KEY)\b",
        r"~/\.ssh/|\bid_rsa\b|~/\.aws/credentials|\.npmrc\b|\.netrc\b",
        r"\bcat\s+[^\n]*\.env\b",
    ],
    # Text telling the agent to act without human confirmation.
    "confirmation_bypass": [
        r"\b(?:do\s+not|don't|never)\s+ask\s+(?:the\s+user\s+)?(?:for\s+)?(?:confirmation|permission|approval)\b",
        r"\bwithout\s+(?:asking|requesting)\s+(?:for\s+)?(?:confirmation|permission|approval)\b",
    ],
    # Classic prompt-injection phrasing embedded in the skill text.
    "injection_phrase": [
        r"\bignore\s+(?:all\s+|any\s+)?(?:previous|prior|above)\s+instructions\b",
    ],
}

SCRIPT_EXT = {".py", ".sh", ".bash", ".zsh", ".js", ".mjs", ".cjs", ".ts",
              ".ps1", ".rb", ".pl", ".go"}

SCRIPT = {
    "proc_exec": [
        r"\bsubprocess\.(?:run|call|Popen|check_output|check_call)\b",
        r"\bos\.(?:system|popen|exec[lv]p?e?)\(",
        r"\bchild_process\b|\bexecSync\(|\bspawnSync?\(",
        r"\bexec\.Command\(",
        r"\bStart-Process\b|\bInvoke-Expression\b",
    ],
    "network": [
        r"\brequests\.(?:get|post|put|delete|request|Session)\b",
        r"\burllib\.request\b|\burlopen\(|\bhttp\.client\b|\bhttpx\.",
        r"\bfetch\(\s*[^)]",
        r"\baxios\b|\bnode-fetch\b|\bhttp\.(?:get|request)\(",
        r"\b(?:curl|wget)\s+",
        r"\bsocket\.socket\(|\bnet\.Dial\(|\bhttp\.(?:Get|Post)\(",
    ],
    "dynamic_code": [
        r"(?<![\w.$])eval\(",
        r"(?<![\w.])exec\((?!\s*\))",
        r"\bnew\s+Function\(",
        r"\bpickle\.loads?\(",
        r"\beval\s+\"?\$",
    ],
    "secrets": [
        r"(?:os\.environ|os\.getenv|process\.env)[^\n]{0,40}(?:KEY|TOKEN|SECRET|PASSWORD)",
        r"~/\.ssh/|\bid_rsa\b|\.aws/credentials|\.npmrc\b|\.netrc\b",
    ],
    "destructive_fs": [
        r"\bshutil\.rmtree\(",
        r"\brm\s+-(?:[a-zA-Z]*r[a-zA-Z]*f|[a-zA-Z]*f[a-zA-Z]*r)\b",
        r"\bfs\.(?:rmSync|rm)\([^)]*recursive",
        r"\bos\.RemoveAll\(",
    ],
    "obfuscation": [
        r"(?:b64decode|atob|base64\s+-d|FromBase64String)[^\n]{0,120}(?:exec|eval|sh\b|iex)",
        r"[A-Za-z0-9+/]{400,}={0,2}",
    ],
}

_INSTR = {k: [re.compile(p, F if k in ("confirmation_bypass", "injection_phrase", "shell_exec") else 0) for p in v]
          for k, v in INSTRUCTION.items()}
_SCRIPT = {k: [re.compile(p) for p in v] for k, v in SCRIPT.items()}


def scan(text, table):
    pats = _INSTR if table == "instruction" else _SCRIPT
    return {k: any(p.search(text) for p in ps) for k, ps in pats.items()}


def first_match(text, category, table):
    pats = (_INSTR if table == "instruction" else _SCRIPT)[category]
    for p in pats:
        m = p.search(text)
        if m:
            s, e = max(0, m.start() - 120), min(len(text), m.end() + 120)
            return text[s:e].replace("\n", " ⏎ ")
    return None
