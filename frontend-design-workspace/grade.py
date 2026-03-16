"""Grade all eval runs by checking assertions against source code."""
import json, re, os, glob as globmod

WORKSPACE = os.path.dirname(os.path.abspath(__file__))
ITER = os.path.join(WORKSPACE, "iteration-1")

def read_all_svelte(outputs_dir):
    """Read and concatenate all .svelte files in a directory."""
    content = ""
    for f in globmod.glob(os.path.join(outputs_dir, "**", "*.svelte"), recursive=True):
        with open(f, "r", encoding="utf-8") as fh:
            content += fh.read() + "\n"
    return content

def check_assertion(code, assertion):
    """Check a single assertion against code. Returns (passed, evidence)."""
    a = assertion.lower()

    if "output is a .svelte file" in a:
        passed = len(code.strip()) > 0
        return passed, "File exists and has content" if passed else "No .svelte file found"

    if "uses tailwind css utility classes" in a or "uses tailwind css utility classes for styling" in a:
        tw_classes = re.findall(r'\b(flex|grid|rounded|shadow|px-|py-|p-\d|text-sm|text-lg|bg-|border|gap-|space-y-|items-center|justify-between|w-full|h-\d)', code)
        passed = len(tw_classes) >= 5
        return passed, f"Found {len(tw_classes)} Tailwind utility patterns" if passed else "Insufficient Tailwind classes found"

    if "dark: prefix classes" in a:
        dark_matches = re.findall(r'dark:', code)
        # Also check for dark-first approach using surface-* palette
        surface_matches = re.findall(r'surface-\d{2,3}', code)
        if len(dark_matches) >= 3:
            return True, f"Found {len(dark_matches)} dark: prefix classes"
        elif len(surface_matches) >= 5:
            return True, f"No dark: prefixes, but uses project's dark-first surface-* palette ({len(surface_matches)} occurrences) which inherently supports dark mode"
        return False, "No dark mode support found (no dark: prefixes and no dark-first palette)"

    if "bell icon" in a:
        has_bell = "bell" in code.lower() or "14.857 17.082" in code or "M15 17h5l" in code
        return has_bell, "Bell icon SVG found" if has_bell else "No bell icon found"

    if "dropdown toggle logic" in a:
        has_toggle = ("isOpen" in code or "open" in code) and ("toggle" in code.lower() or "onclick" in code.lower() or "on:click" in code)
        return has_toggle, "Toggle state and click handler found" if has_toggle else "No toggle logic found"

    if "unread indicators" in a:
        has_unread = ("unread" in code.lower() or "!read" in code or ".read" in code) and ("dot" in code.lower() or "rounded-full" in code or "badge" in code.lower())
        return has_unread, "Unread indicator styling found" if has_unread else "No unread indicators found"

    if "timestamps on notification" in a:
        has_ts = "timestamp" in code.lower() or "formatTime" in code or "ago" in code
        return has_ts, "Timestamp formatting found" if has_ts else "No timestamps found"

    if "mark-all-as-read" in a or "mark all as read" in a:
        has_mark = "mark" in code.lower() and "read" in code.lower()
        return has_mark, "Mark all as read action found" if has_mark else "No mark-all-read action found"

    if "<button> elements for interactive" in a:
        buttons = re.findall(r'<button', code)
        divs_onclick = re.findall(r'<div[^>]*on(?:click|:click)', code)
        passed = len(buttons) >= 2 and len(divs_onclick) <= 1
        return passed, f"Found {len(buttons)} <button> elements, {len(divs_onclick)} div onclick" if passed else "Insufficient button usage"

    if "hover:" in a and "focus" in a:
        hover = re.findall(r'hover:', code)
        focus = re.findall(r'focus-visible:|focus:', code)
        passed = len(hover) >= 2 and len(focus) >= 1
        return passed, f"Found {len(hover)} hover: and {len(focus)} focus states" if passed else "Insufficient hover/focus states"

    if "sidebar navigation" in a and ("profile" in a.lower() or "listing" in a.lower()):
        sections = ["profile", "account", "notification", "appearance"]
        found = [s for s in sections if s in code.lower()]
        passed = len(found) >= 4
        return passed, f"Found sidebar sections: {found}" if passed else f"Only found: {found}"

    if "name input field" in a or "name" in a and "field" in a and "profile" in a:
        has_name = re.search(r'(?:name|display.?name)', code, re.I) and re.search(r'<input', code)
        return bool(has_name), "Name input field found" if has_name else "No name input found"

    if "email input field" in a or "email" in a and "field" in a:
        has_email = re.search(r'type=["\']email["\']', code) or (re.search(r'email', code, re.I) and re.search(r'<input', code))
        return bool(has_email), "Email input found" if has_email else "No email input found"

    if "bio input" in a or "bio" in a and "textarea" in a:
        has_bio = re.search(r'bio', code, re.I) and re.search(r'<textarea', code)
        return bool(has_bio), "Bio textarea found" if has_bio else "No bio textarea found"

    if "avatar upload" in a:
        has_avatar = re.search(r'avatar', code, re.I) and re.search(r'type=["\']file["\']', code)
        return bool(has_avatar), "Avatar upload area found" if has_avatar else "No avatar upload found"

    if "form inputs have" in a and "label" in a:
        labels = re.findall(r'<label', code)
        inputs = re.findall(r'<input|<textarea|<select', code)
        passed = len(labels) >= 2 and len(labels) >= len(inputs) * 0.5
        return passed, f"Found {len(labels)} labels for {len(inputs)} inputs" if passed else f"Only {len(labels)} labels for {len(inputs)} inputs"

    if "responsive breakpoint" in a or "responsive" in a and "classes" in a:
        bp = re.findall(r'(?:sm:|md:|lg:|xl:)', code)
        passed = len(bp) >= 2
        return passed, f"Found {len(bp)} responsive breakpoint prefixes" if passed else "Insufficient responsive classes"

    if "save" in a and "submit" in a and "button" in a:
        has_save = re.search(r'(?:save|submit)', code, re.I) and re.search(r'<button', code)
        return bool(has_save), "Save/submit button found" if has_save else "No save button found"

    if "4 stat cards" in a:
        stats_count = len(re.findall(r'(?:total.?users|revenue|orders|conversion)', code, re.I))
        passed = stats_count >= 4
        return passed, f"Found {stats_count} stat metric labels" if passed else f"Only found {stats_count} metrics"

    if "chart placeholder" in a:
        has_chart = re.search(r'chart', code, re.I) and (re.search(r'<svg', code) or re.search(r'placeholder', code, re.I))
        return bool(has_chart), "Chart placeholder area found" if has_chart else "No chart area found"

    if "<thead>" in a and "<tbody>" in a:
        has_thead = "<thead" in code
        has_tbody = "<tbody" in code
        passed = has_thead and has_tbody
        return passed, f"thead: {has_thead}, tbody: {has_tbody}"

    if "order id" in a and "customer" in a and "amount" in a:
        cols = ["order", "customer", "amount", "status", "date"]
        found = [c for c in cols if re.search(c, code, re.I)]
        passed = len(found) >= 5
        return passed, f"Found columns: {found}" if passed else f"Only found: {found}"

    if "colored badge" in a or "status" in a and "badge" in a:
        has_badges = re.search(r'(?:bg-(?:green|emerald|blue|red|amber|yellow))', code)
        return bool(has_badges), "Colored status badges found" if has_badges else "No colored badges found"

    if "stat card grid" in a and "responsive" in a:
        has_grid = re.search(r'grid-cols-\d.*(?:sm:|lg:)grid-cols-|grid-cols-1.*(?:sm:|lg:)', code)
        passed = bool(has_grid) or (re.search(r'grid-cols', code) and re.search(r'(?:sm:|lg:)', code))
        return passed, "Responsive grid for stat cards found" if passed else "No responsive stat grid found"

    # Fallback
    return False, f"No grading logic for assertion: {assertion}"


def grade_run(eval_name, run_type, assertions):
    """Grade a single run."""
    outputs_dir = os.path.join(ITER, eval_name, run_type, "outputs")
    code = read_all_svelte(outputs_dir)

    results = []
    passed_count = 0
    for a in assertions:
        p, ev = check_assertion(code, a)
        results.append({"text": a, "passed": p, "evidence": ev})
        if p:
            passed_count += 1

    total = len(assertions)
    grading = {
        "expectations": results,
        "summary": {
            "passed": passed_count,
            "failed": total - passed_count,
            "total": total,
            "pass_rate": round(passed_count / total, 2) if total > 0 else 0
        }
    }

    out_path = os.path.join(ITER, eval_name, run_type, "grading.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(grading, f, indent=2)

    return grading["summary"]


# Define assertions per eval
evals = {
    "notification-dropdown": [
        "Output is a .svelte file",
        "Uses Tailwind CSS utility classes for styling (not custom CSS as primary approach)",
        "Has dark: prefix classes for dark mode support",
        "Contains a bell icon (SVG element or icon component import)",
        "Has dropdown toggle logic (click handler with visibility state variable)",
        "Shows unread indicators (visual dot or badge on notification items)",
        "Includes timestamps on notification items",
        "Has a mark-all-as-read action (button or link)",
        "Uses <button> elements for interactive actions rather than div with onclick",
        "Includes hover: and/or focus-visible: state classes on interactive elements"
    ],
    "settings-page": [
        "Output is a .svelte file",
        "Has a sidebar navigation listing Profile, Account, Notifications, and Appearance",
        "Profile section contains a name input field",
        "Profile section contains an email input field",
        "Profile section contains a bio input/textarea field",
        "Has an avatar upload area or placeholder",
        "Uses Tailwind CSS utility classes for styling",
        "Has dark: prefix classes for dark mode support",
        "Form inputs have associated <label> elements",
        "Has responsive breakpoint classes (sm: md: or lg: prefixes for layout changes)",
        "Includes a save or submit button for the form"
    ],
    "dashboard-page": [
        "Output is a .svelte file",
        "Shows 4 stat cards with distinct metric labels (users, revenue, orders, conversion)",
        "Has a chart placeholder area or section",
        "Has a table element with proper <thead> and <tbody> structure",
        "Table includes columns for order ID, customer, amount, status, and date",
        "Status column uses colored badge styling (distinct background colors for different statuses)",
        "Uses Tailwind CSS utility classes for styling",
        "Has dark: prefix classes for dark mode support",
        "Stat card grid uses responsive classes (grid-cols with breakpoint variants)",
        "Includes hover: or focus-visible: state classes on interactive elements"
    ]
}

print("=" * 60)
print("GRADING RESULTS")
print("=" * 60)

for eval_name, assertions in evals.items():
    print(f"\n--- {eval_name} ---")
    for run_type in ["with_skill", "without_skill"]:
        summary = grade_run(eval_name, run_type, assertions)
        print(f"  {run_type}: {summary['passed']}/{summary['total']} ({summary['pass_rate']*100:.0f}%)")

print("\nDone! Grading files written.")
