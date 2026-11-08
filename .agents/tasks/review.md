# Demo Account Dormitory Recommendations Fix

The fix adds fallback to hardcoded demo property data when the logged-in user is a demo account (demostudent@gmail.com or demoowner@gmail.com) or when the app runs on GitHub Pages (no backend available). The immediate problem—demo students seeing no recommendations on the Overview tab—is addressed by ensuring demo properties render when API calls fail or when demo mode is detected.

**Watch for:** Demo mode detection is now duplicated across multiple functions, increasing the risk of inconsistent behavior if the logic needs to change later. The distinction between "demo account" and "GitHub Pages" is blurred in several places, making it unclear whether both conditions should trigger demo mode or just demo accounts. localStorage-based saved dorms and messages aren't persisted to backend in demo mode, so state is lost on refresh.

**Verdict**: APPROVED

---

## High-level view

Demo mode is now triggered both by recognizing demo account emails and by detecting GitHub Pages deployment. Three centralized helper functions handle API fallback: `isDemoMode()` detects whether to use demo data, `fetchWithDemoFallback()` and `postWithDemoFallback()` wrap GET and POST requests to return demo data when the backend is unavailable. The demo properties array is hardcoded in the student dashboard with sufficient fields (name, type, address, price, image, amenities, rules) to render dorm cards. The Overview tab's recommended section, Browse tab, and detail view all call through `fetchAllProperties()`, which now checks for demo mode and returns the hardcoded data immediately, bypassing the API. Bookings, messages, and saved dorms all have demo fallback paths, though saved dorms remain client-side only and don't persist. The backend's Flask `/api/properties` endpoint also returns demo data for demo accounts, providing consistency if the frontend ever makes a real API call.

---

<details>
<summary>Issues (3)</summary>

1. **Duplicate demo-mode logic across functions** — `isDemoMode()`, `fetchAllProperties()`, `fetchStudentBookings()`, `fetchUserMessages()`, and several others each contain independent checks for demo accounts and GitHub Pages. If the demo account list or detection criteria need to change, every function must be updated. Consolidate to a single source of truth.

2. **Unclear demo-vs-GitHub-Pages semantics** — Functions check both demo accounts and GitHub Pages as separate conditions ORed together, but it's not documented why. Should GitHub Pages *always* use demo mode, or only when no backend is available? Clarify whether these are fallback levels or equivalent triggers.

3. **Saved dorms not persisted in demo mode** — Demo students can favorite dorms and see them in the Saved tab, but favorites are stored only in `savedDormsList` (in-memory). On page refresh or logout, all saved dorms are lost. Consider using localStorage or the `/api/bookmarks` endpoint to persist (though the Flask backend doesn't currently have a bookmarks table).

</details>

---

<details>
<summary>Details</summary>

### Demo property data is complete enough to render cards

The `DEMO_PROPERTIES` array is hardcoded with all required fields for the dorm cards to render: `name`, `type`, `address`, `rent`, `image`, `amenities`, and `rules`. Each demo property includes plausible values (e.g., "Demo Dorm - Minglanilla Heights" at ₱5,000/month, with Wi-Fi, Common Room, Kitchen, Laundry amenities). When `renderStudentDorms(allDatabaseProperties)` is called, it iterates over the properties and generates `.dorm-card` divs with background images, ratings, and price badges. The image URLs point to Unsplash, so images should load on GitHub Pages (confirmed: no local paths). The array has three properties, which fills the dorms grid without looking empty.

### Recommendations section on Overview tab now populates with demo data

The Overview tab's "Recommended for you" section calls `renderStudentDorms(allDatabaseProperties)` via `fetchAllProperties()`. When `isDemoMode()` returns true (demo account or GitHub Pages), `fetchAllProperties()` assigns `allDatabaseProperties = DEMO_PROPERTIES` and calls `renderStudentDorms()` immediately without attempting an API call. The grid renders the three demo properties. This addresses the reported bug: demostudent@gmail.com signing in on GitHub Pages now sees demo dorms.

### All API calls have demo fallback paths, but inconsistently

**Confirmed**: `fetchAllProperties()`, `fetchStudentBookings()`, `fetchUserMessages()`, `submitBookingRequest()`, `submitMessageToOwner()`, and `saveProfileChanges()` all check for demo mode and return demo data or success responses without making real API calls.

**Likely issue**: The logic differs slightly between functions. Some (e.g., `fetchAllProperties()`) check both `isDemoAccount` and `isGitHubPages` inline, while others call `isDemoMode()`. Some wrap in `postWithDemoFallback()`, others inline the check. If demo-mode behavior needs to change—for example, to allow GitHub Pages users to try real API calls with fallback—many locations would need updates. The helper functions `fetchWithDemoFallback()` and `postWithDemoFallback()` are defined but not used everywhere they could be; for example, `fetchUserMessages()` inlines the check instead of calling `fetchWithDemoFallback()`.

### No unrelated changes bundled

The diff touches only student-dashboard.html and signin.html to add/modify demo detection and fallback logic. No reformatting, no dependency changes, no unrelated features.

### Local development with localhost is unaffected

For users running the Flask backend on localhost:5000, `window.location.hostname` is "localhost" or "127.0.0.1", so `window.location.hostname.includes('github.io')` returns false. The demo mode condition checks `isDemoAccount || isGitHubPages`, so non-demo users on localhost skip demo mode and attempt real API calls. This is correct behavior.

### Demo bookings and messages are hardcoded but not editable

Demo students see a single hardcoded booking and a sample conversation in the Bookings and Messages tabs. When a demo student submits a new booking or sends a message, the `postWithDemoFallback()` logic returns `success: true` without persisting. Subsequent calls to `fetchStudentBookings()` or `fetchUserMessages()` return the same hardcoded arrays. This is acceptable for a demo—users see realistic data without backend—but it means demo actions appear to succeed but are not reflected in future views, which could be confusing.

### Backend provides demo data for demo accounts too

The Flask backend's `/api/properties`, `/api/bookings`, and `/api/messages` endpoints all check if the email is a demo account (`demostudent@gmail.com` or `demoowner@gmail.com`) and return hardcoded demo arrays. This is consistent with the frontend. If a demo student's browser somehow makes a real API call (e.g., after backend is restored), they'll get demo data. However, the backend checks happen *after* the frontend's demo mode check, so in practice the frontend returns demo data before the API is called.

### isDemoMode() function is defined but not consistently used

**Confirmed**: `isDemoMode()` is defined at line ~550 and checks both demo account and GitHub Pages. However, most functions that need demo-mode detection reimplement the check inline instead of calling `isDemoMode()`. For example, `fetchAllProperties()` (line ~590) does:
```javascript
const isDemoAccount = userEmail === 'demostudent@gmail.com' || userEmail === 'demoowner@gmail.com';
if (isDemoAccount || window.location.hostname.includes('github.io')) {
  allDatabaseProperties = DEMO_PROPERTIES;
  ...
}
```
instead of:
```javascript
if (isDemoMode()) {
  allDatabaseProperties = DEMO_PROPERTIES;
  ...
}
```
This duplication works but violates DRY and makes the code harder to maintain. If the demo account list changes, every occurrence must be updated.

### Syntax and logic are valid

No syntax errors detected: all brackets are closed, all function calls have correct signatures, and the JavaScript parses correctly. The logic correctly assigns demo data when conditions are met and attempts real API calls otherwise.

</details>

---

## File map

<details>
<summary>Changes</summary>

- **student-dashboard.html** — Added `DEMO_PROPERTIES`, `DEMO_BOOKINGS_STUDENT`, and `DEMO_MESSAGES_STUDENT` hardcoded arrays. Added `isDemoMode()` helper to detect demo accounts or GitHub Pages. Modified `fetchAllProperties()` to check demo mode and return demo data immediately. Updated `fetchStudentBookings()`, `fetchUserMessages()`, `submitBookingRequest()`, `submitMessageToOwner()`, and `saveProfileChanges()` to include demo-mode fallback logic. Added `fetchWithDemoFallback()` and `postWithDemoFallback()` helper wrappers (partially used).

- **signin.html** — No changes to core logic. Demo accounts section remains in the info box. Demo account check in the form submission is unchanged (already present in base).

- **apy.py** — Backend's `/api/properties`, `/api/bookings`, and `/api/messages` endpoints already check for demo accounts and return hardcoded demo data. No new changes needed.

Full diff: [git diff](https://github.com/your-repo/commit/abc123)

</details>
