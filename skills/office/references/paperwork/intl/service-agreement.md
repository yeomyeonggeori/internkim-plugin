# Service Agreement

output: docx
filename: Service_Agreement_<provider-name>_<YYYYMMDD>.docx

## Purpose

An editable draft agreement under which a Client engages a Provider to perform defined services for a fee, for review before execution.

## Required fields

- parties: company name, registration number, address, and representative for both Client and Provider
- scope: specific description of the services to be performed
- term: agreement period (start date to end date)
- fees: total fee amount, payment schedule (amount and timing per installment), payment method, whether tax is included or additional
- ip: ownership of deliverables and intellectual property (commonly assigned to the Client on full payment, but confirm with the requester)
- date, signatures of both parties

## Document JSON skeleton

```json
{
  "form": "intl/service-agreement",
  "title": "Service Agreement",
  "page": { "marginInches": 0.9 },
  "blocks": [
    { "type": "paragraph", "text": "This Service Agreement (this \"Agreement\") is entered into by and between <client name> (\"Company\") and <provider name> (\"Provider\")." },
    { "type": "heading", "level": 1, "text": "1. Purpose" },
    { "type": "paragraph", "text": "This Agreement sets out the rights and obligations of the Company and the Provider in connection with the Company's engagement of the Provider to perform <service name> (the \"Services\")." },
    { "type": "heading", "level": 1, "text": "2. Scope of Services" },
    { "type": "paragraph", "text": "The Provider shall perform the following Services:" },
    { "type": "bullets", "items": ["<service item 1>", "<service item 2>", "<service item 3>"] },
    { "type": "heading", "level": 1, "text": "3. Term" },
    { "type": "paragraph", "text": "This Agreement is effective from <YYYY-MM-DD> through <YYYY-MM-DD>. Any extension requires the written agreement of both parties." },
    { "type": "heading", "level": 1, "text": "4. Fees and Payment" },
    { "type": "paragraph", "text": "The total fee for the Services is <amount> (tax inclusive/exclusive), payable according to the following schedule." },
    { "type": "table", "columnWidthsInches": [1.5, 2.5, 2.6], "rows": [
      ["Installment", "Payment date", "Amount"],
      ["Deposit", "<payment date>", "<amount>"],
      ["Balance", "<payment date>", "<amount>"]
    ] },
    { "type": "paragraph", "text": "Payment shall be made to the account designated by the Provider (<provider bank account details>)." },
    { "type": "heading", "level": 1, "text": "5. Deliverables and Intellectual Property" },
    { "type": "paragraph", "text": "Intellectual property rights in the deliverables produced by the Provider under this Agreement shall transfer to the Company upon full payment of the fees. Rights in materials and tools the Provider held prior to this engagement remain with the Provider." },
    { "type": "heading", "level": 1, "text": "6. Confidentiality" },
    { "type": "paragraph", "text": "Each party shall not disclose to any third party, or use for any purpose outside this Agreement, confidential information of the other party obtained in the course of performing this Agreement, without the other party's prior written consent." },
    { "type": "heading", "level": 1, "text": "7. Changes and Termination" },
    { "type": "paragraph", "text": "Any change to this Agreement requires the written agreement of both parties. If either party breaches this Agreement and fails to cure the breach within a reasonable period after notice, the other party may terminate this Agreement by written notice." },
    { "type": "heading", "level": 1, "text": "8. Liability" },
    { "type": "paragraph", "text": "A party that breaches this Agreement and thereby causes damage to the other party shall be liable for such damage, subject to any limitation the parties have agreed in writing." },
    { "type": "heading", "level": 1, "text": "9. Governing Law and Jurisdiction" },
    { "type": "paragraph", "text": "This Agreement is governed by the laws of <governing law jurisdiction>. Any dispute arising from this Agreement is subject to the exclusive jurisdiction of <competent court>." },
    { "type": "paragraph", "text": "IN WITNESS WHEREOF, the parties have executed this Agreement in duplicate, each party retaining one signed copy." },
    { "type": "paragraph", "text": "<Month D, YYYY>" },
    { "type": "table", "columnWidthsInches": [1.2, 2.7, 2.7], "rows": [
      ["", "Company", "Provider"],
      ["Legal name", "<client legal name>", "<provider legal name>"],
      ["Address", "<client address>", "<provider address>"],
      ["Representative", "<client representative>  Signature: ____________________", "<provider representative>  Signature: ____________________"]
    ] }
  ]
}
```

## Fixed wording

- Execution sentence: "IN WITNESS WHEREOF, the parties have executed this Agreement in duplicate, each party retaining one signed copy."
- Article order (Purpose, Scope of Services, Term, Fees and Payment, Deliverables and Intellectual Property, Confidentiality, Changes and Termination, Liability, Governing Law and Jurisdiction) is the default; renumber sequentially if the requester adds or removes an article.

## Rules

- Never invent names, amounts, durations, or governing law — use only requester-provided facts and ask when a required field is missing.
- Amounts are written with thousands separators, and tax-inclusive vs. tax-exclusive status is always stated.
- If the requester specifies different intellectual-property ownership (e.g. retained by the Provider), adjust Article 5 accordingly rather than defaulting to Client ownership.
- This document is a draft for legal review; say so when delivering it.
