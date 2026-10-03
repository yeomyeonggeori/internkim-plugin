File by business function in a category without children or X. A parent without children is a filing destination. A parent grant includes current and future children.

| Code | Category | Parent | Scope |
|---|---|---|---|
| `C` | Corporate | — | Legal entity, ownership and corporate decisions. |
| `CR` | Registration | C | Formation, articles, registrations and legal entity records. |
| `CO` | Ownership | C | Shareholder registers, capitalization tables and ownership records. |
| `CG` | Governance | C | Board and shareholder decisions, minutes and delegated authorities. |
| `H` | Human resources | — | Employment, organization and employee records. |
| `HO` | Organization | H | Organization charts, job descriptions and aggregate workforce information. |
| `HP` | Employment policies | H | Employment rules, benefits policies and employee handbooks. |
| `HE` | Employment records | H | Individual employment agreements, onboarding, leave and departure records. Payroll payments belong to FP. |
| `HR` | Recruiting | H | Job postings, applications and hiring records. |
| `HA` | Appraisals | H | Individual performance, disciplinary and development records. |
| `F` | Finance | — | Financial position, accounting, tax and payments. |
| `FS` | Financial statements | F | Financial statements, financial audit reports and consolidated results. Supporting accounting evidence belongs to FA. |
| `FB` | Budgets | F | Budgets, financial forecasts and financial models. |
| `FT` | Tax | F | Tax returns, assessments and tax authority correspondence. Employee withholding belongs to FP. |
| `FC` | Cash and banking | F | Bank statements, payments, treasury and account documentation. Excludes credentials and financing agreements, which belong to RA. |
| `FA` | Accounting evidence | F | Ledgers, invoices, receipts and accounting evidence. Underlying contracts follow the relationship. |
| `FP` | Payroll | F | Payroll registers, payslips, payroll calculations and employee tax withholding. Employment terms belong to HE. |
| `S` | Sales and marketing | — | Customers, commercial partnerships and market-facing work. |
| `SS` | Sales materials | S | Proposals, quotes, sales materials and commercial analysis. Fundraising presentations belong to RP. |
| `SM` | Marketing | S | Brand assets, campaigns, advertising and market research, including images and video. |
| `SC` | Customer records | S | Customer agreements, orders, correspondence and service records. Invoice originals belong to FA. |
| `SP` | Commercial partners | S | Distribution, referral and commercial partnership records. Procurement belongs to OS. |
| `P` | Products and services | — | What the company delivers to customers. |
| `PO` | Product overview | P | Product and service descriptions, catalogs and user-facing manuals. Persuasive sales materials belong to SS. |
| `PD` | Development | P | Specifications, designs, architecture, roadmaps and development records. |
| `PQ` | Quality | P | Testing, quality control, defects and acceptance records. Formal certifications belong to LC. |
| `O` | Operations | — | Operating the company, facilities, procurement and internal systems. |
| `OP` | Operating procedures | O | Internal operating procedures and continuity plans. Employment rules belong to HP and security policies to LS. |
| `OA` | Assets and facilities | O | Asset registers, premises, leases, equipment and maintenance records. |
| `OS` | Suppliers | O | Procurement, supplier agreements, correspondence and supply-chain records. |
| `OI` | Internal IT | O | Internal IT administration, software subscriptions and routine incidents. Security incidents belong to LS. Never store credentials. |
| `I` | Intellectual property | — | Ownership, registration and licensing of intellectual property. |
| `IR` | IP rights | I | Patents, trademarks, copyright ownership and intellectual property registrations. |
| `IL` | IP licenses | I | Grants, assignments and acquisition of IP rights. Routine software subscriptions belong to OI. |
| `L` | Legal and compliance | — | Legal obligations, regulation and risk. |
| `LC` | Regulatory compliance | L | Permits, certifications, regulatory filings and compliance assessments. |
| `LS` | Security and privacy | L | Security and privacy policies, assessments and incidents. |
| `LD` | Disputes | L | Claims, litigation, legal opinions and dispute records. |
| `LI` | Insurance | L | Insurance policies, coverage and claims. |
| `R` | Raising capital | — | Raising equity or debt and communicating with capital providers. |
| `RP` | Financing presentations | R | Fundraising decks and investment or financing narratives. Source financial statements remain in FS. |
| `RA` | Financing agreements | R | Equity and debt agreements, term sheets and financing negotiations. Resulting ownership registers belong to CO and resolutions to CG. |
| `RR` | Investor reporting | R | Investor and lender updates and correspondence outside agreement negotiations. |
| `G` | General company records | — | Company-wide records outside a specific business function; not miscellaneous storage. |
| `GP` | Company profile | G | Company introductions, history, mission and general company plans. Financing presentations belong to RP. |
| `GC` | Company communications | G | General company announcements and communication records. |
| `GE` | Company events | G | Company events and culture records, including event photos and recordings. |
| `X` | Inbox | — | Unclassified or ambiguous documents. Choose X when context does not identify a destination. Do not invent missing facts. |

## Default circles

Each circle names an array of category codes. Belonging to several circles combines them. Add circles or edit these defaults.

| Circle | Name | readableCategories |
|---|---|---|
| `member` | Member | [HO, HP, PO, GP, GC, GE] |
| `leadership` | Leadership | [C, H, F, S, P, O, I, L, R, G, X] |
| `finance` | Finance | [CR, F, SC, SP, OA, OS, LI, RA, RR] |
| `human-resources` | HR | [CR, H, FP, GP, GC, GE] |
| `investor` | Investor | [CR, CO, FS, FB, PO, RP, RR, GP] |
| `accountant` | Accountant | [CR, F, SC, SP, OA, OS, LI, RA] |
| `legal` | Legal adviser | [C, HP, HE, SC, SP, OA, OS, I, L, RA] |
| `lender` | Lender | [CR, CO, FS, FB, FT, FC, RA, RR, GP] |
