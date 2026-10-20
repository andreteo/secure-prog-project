<!-- One section between horizontal rules is one PowerPoint slide. Speaker cues and layout suggestions are in HTML comments so they do not appear on the slide. Aim for about five minutes, plus the live demo. -->

# Book Ledger

## Learning secure programming by testing our own app

**600IT Secure Programming**  
Build a weak version → test it → add controls → repeat the tests

<!-- Visual: One large title and the four-step line. Keep the cover otherwise empty. Speaker cue: “Our goal was not to build the most feature-rich ebook tracker. We built a small system so we could see exactly what changes when security checks move into the server.” -->

---

# The experiment

**React browser → Flask API → SQLite books and private notes**

The browser can choose a URL, search term or request body.  
**The API must decide whether that request is allowed.**

We used the same demo accounts and repeated the same misuse cases before and after adding controls.

<!-- Visual: Draw the three components as one left-to-right line. Mark the browser-to-API arrow as the trust boundary. Speaker cue: “The interface is useful, but it cannot prove identity or ownership. We tested what happens when someone sends requests directly or changes a URL.” -->

---

# What failed in the baseline

- A known username was enough to sign in.
- Changing the user ID in the URL revealed another reader's library.
- Search accepted SQL that could change stored books; the admin API exposed all records.

![Baseline: signed in as Doon while the URL displays Otherdoon's library](media/Pasted%20image%2020261013110140.png)

<!-- Visual: Give the screenshot most of the slide. The address bar, “Signed in as Doon,” and “Otherdoon’s library” are the three details to point out. Speaker cue: “These weaknesses were intentional and used synthetic data. The screenshot shows why hiding a link or trusting the page state is not an access check.” -->

---

# What we changed at the API

**Identity** — Password hashes and expiring server-validated sessions  
**Access** — Ownership and administrator role checked on each request  
**Input** — Parameterized SQL, book-field validation and CSRF checks for writes  
**Abuse and transport** — Login throttling and local HTTPS with protected cookies

<!-- Visual: Use four large horizontal rows, not code screenshots. Highlight “at the API.” Speaker cue: “Each control answers a different question. A valid session says who is calling; it does not say whose book they may open.” Guidance used in the report includes OWASP ASVS and NIST SP 800-63B-4. -->

---

# The same requests produced different outcomes

| Test | Weak version | Secured version |
| --- | --- | --- |
| Sign in | Known username accepted | Wrong password → **401** |
| Open another user's library | Private notes shown | **404**; notes stay private |
| Call admin API as a reader | All books returned | **403** |
| Submit SQL through search | SQL could run | Treated as search text; rows unchanged |
| Repeat login requests | No limit | Sixth request in one minute → **429** |

**We checked HTTP results and stored data, not only what the page displayed.**

<!-- Speaker cue: “For a write attempt, a failure message alone is not enough. We also checked that the other reader’s book had not changed. The 429 threshold is per IP in this local, single-process demo.” -->

---

# What we can show live

1. Sign in as **doon** and open Doon's library.
2. Change `/users/1/dashboard` to `/users/2/dashboard` → **404**.
3. Enter SQL-like text in search → no other user's book appears or changes.

**Optional:** show an ordinary user receiving **403** at `/api/admin/books`, or repeated login requests reaching **429**.

<!-- Visual: Present the three actions as a simple sequence. Keep browser Network open for the response codes. Use the insecure screenshots to show the “before” result, then perform the secured requests live. Avoid displaying session cookie values or CSRF tokens. -->

---

# What we learned

- A sign-in screen does not establish security; the server must verify identity and permission.
- Different controls solve different problems: ownership, SQL parameters, validation, throttling and HTTPS work together.
- A convincing security claim needs a repeatable attack, an observed response and, for writes, an unchanged database.

**Scope:** seeded demo accounts, local HTTPS and an in-memory per-IP limiter. This is a controlled learning experiment.

<!-- Visual: End on the three lessons, not a new feature list. Speaker cue: “The point of the project is that we can explain what each basic control prevents, demonstrate it, and state what our small local test does not prove.” -->
