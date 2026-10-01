# Non-Disclosure Agreement (NDA)

output: docx
filename: NDA_<counterparty>_<YYYYMMDD>.docx

## Purpose

An agreement protecting confidential information shared between two parties for a deal, negotiation, or joint project review. Confirm with the requester whether this is one-way (only one party discloses) or mutual (both parties disclose) before drafting.

## Required fields

- parties: company name, registration number, address, and representative for both Party A and Party B
- disclosureType: one-way (only the Receiving Party receives confidential information) or mutual (both parties receive) — must be confirmed with the requester
- purpose: the purpose for which confidential information is shared (e.g. "evaluating a potential partnership")
- term: agreement term (years), survival period of confidentiality obligations after termination (n years)
- date, signatures of both parties

## Document JSON skeleton

```json
{
  "title": "Non-Disclosure Agreement",
  "fontName": "Pretendard",
  "fontSize": 10.5,
  "page": { "marginInches": 0.9 },
  "blocks": [
    { "type": "paragraph", "text": "This Non-Disclosure Agreement (this \"Agreement\") is entered into by and between <Party A name> (\"Party A\") and <Party B name> (\"Party B\") in connection with <purpose of discussion>, to protect the confidential information the parties provide to one another." },
    { "type": "heading", "level": 1, "text": "1. Purpose" },
    { "type": "paragraph", "text": "This Agreement sets out the terms under which the parties will protect confidential information disclosed to or obtained from each other in the course of <purpose of discussion>." },
    { "type": "heading", "level": 1, "text": "2. Definition of Confidential Information" },
    { "type": "paragraph", "text": "\"Confidential Information\" means the following categories of information disclosed by one party to the other in writing, orally, or electronically in connection with this Agreement." },
    { "type": "bullets", "items": ["Technical information (designs, source code, know-how, R&D materials)", "Business information (business plans, pricing, marketing strategy)", "Customer and business partner information", "Financial and other management information"] },
    { "type": "paragraph", "text": "Confidential Information excludes information that:" },
    { "type": "bullets", "items": ["was already public at the time of disclosure", "was already rightfully known to the receiving party before disclosure", "was independently developed by the receiving party without use of the Confidential Information", "was rightfully obtained by the receiving party from a third party with authority to disclose it"] },
    { "type": "heading", "level": 1, "text": "3. Obligations" },
    { "type": "paragraph", "text": "<Party B / Both parties> shall use the Confidential Information solely for the purpose of this Agreement and shall not disclose it to any third party without the prior written consent of the disclosing party. Access shall be limited to employees who need it, and those employees shall be bound by confidentiality obligations no less protective than this Agreement." },
    { "type": "heading", "level": 1, "text": "4. Exceptions" },
    { "type": "paragraph", "text": "Where disclosure of Confidential Information is required by law or by a court or governmental order, the receiving party shall notify the disclosing party in advance where practicable and disclose only the minimum necessary." },
    { "type": "heading", "level": 1, "text": "5. Return or Destruction" },
    { "type": "paragraph", "text": "Upon termination of this Agreement or upon the disclosing party's written request, the receiving party shall promptly return or destroy all Confidential Information and copies thereof, and shall provide written confirmation of destruction upon request." },
    { "type": "heading", "level": 1, "text": "6. Term and Survival" },
    { "type": "paragraph", "text": "This Agreement is effective for <n> years from the date of execution. The confidentiality obligations survive termination of this Agreement for <m> years." },
    { "type": "heading", "level": 1, "text": "7. Remedies" },
    { "type": "paragraph", "text": "A party that breaches this Agreement and thereby causes damage to the other party shall be liable for such damage." },
    { "type": "heading", "level": 1, "text": "8. Governing Law and Jurisdiction" },
    { "type": "paragraph", "text": "This Agreement shall be governed by the laws of <governing law>. Any dispute arising from this Agreement shall be subject to the exclusive jurisdiction of <competent court>." },
    { "type": "paragraph", "text": "IN WITNESS WHEREOF, the parties have executed this Agreement in duplicate, each party retaining one signed copy." },
    { "type": "paragraph", "text": "<Month D, YYYY>" },
    { "type": "table", "columnWidthsInches": [1.2, 2.7, 2.7], "rows": [
      ["", "Party A", "Party B"],
      ["Company", "<Party A name>", "<Party B name>"],
      ["Address", "<Party A address>", "<Party B address>"],
      ["Representative", "<Party A representative>", "<Party B representative>"]
    ] }
  ]
}
```

## Fixed wording

- Execution sentence: "IN WITNESS WHEREOF, the parties have executed this Agreement in duplicate, each party retaining one signed copy."
- Article 6 must state the agreement term and the survival period separately.

## Rules

- Confirm with the requester whether this is one-way or mutual disclosure before drafting; if one-way, adjust Article 3 so the obligation falls on the receiving party only.
- Never invent party names, addresses, amounts, durations, or governing law — use only requester-provided facts, and ask when any are missing.
- This document is a draft for legal review; say so when delivering it.
