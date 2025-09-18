--------------- Same signer twice: ----------

https://diavgeia.gov.gr/opendata/signers/100068713
<signer>
<uid>100068713</uid>
<firstName>ΑΘΑΝΑΣΙΑ</firstName>
<lastName>ΞΕΠΑΠΑΔΑΚΟΥ</lastName>
<active>true</active>
<activeFrom>2021-09-14T03:00:00+03:00</activeFrom>
<activeUntil>3000-01-01T00:00:00.061+02:00</activeUntil>
<organizationId>50013</organizationId>
<hasOrganizationSignRights>false</hasOrganizationSignRights>
<units>
<unit>
<positionId>POS_10077</positionId>
<positionLabel>Αντιπρόεδρος Δ.Σ.</positionLabel>
<uid>72491</uid>
</unit>
</units>
</signer>

and

https://diavgeia.gov.gr/opendata/signers/100068714:

<signer>
<uid>100068714</uid>
<firstName>ΑΘΑΝΑΣΙΑ</firstName>
<lastName>ΞΕΠΑΠΑΔΑΚΟΥ</lastName>
<active>true</active>
<activeFrom>2021-09-14T03:00:00+03:00</activeFrom>
<activeUntil>3000-01-01T00:00:00.371+02:00</activeUntil>
<organizationId>50013</organizationId>
<hasOrganizationSignRights>false</hasOrganizationSignRights>
<units>
<unit>
<positionId>POS_10077</positionId>
<positionLabel>Αντιπρόεδρος Δ.Σ.</positionLabel>
<uid>72491</uid>
</unit>
</units>
</signer>


----------------------


--------------------------------

Signers without real names:

100031708	ΠΡΟΪΣΤΑΜΕΝΟΣ ΔΙΕΥΘΥΝΣΗΣ	ΔΙΕΥΘΥΝΣΗ ΔΙΟΙΚΗΤΙΚΟΥ & ΛΕΙΤΟΥΡΓΙΚΗΣ ΥΠΟΣΤΗΡΙΞΗΣ
100079312	ΠΡΟΪΣΤΑΜΕΝΟΣ ΔΙΕΥΘΥΝΣΗΣ	ΔΙΕΥΘΥΝΣΗ ΗΛΕΚΤΡΟΝΙΚΗΣ ΔΙΑΚΥΒΕΡΝΗΣΗΣ
104027	ΔΙΕΥΘΥΝΤΗΣ	ΔΙΕΥΘΥΝΣΗ ΟΙΚΟΝΟΜΙΚΩΝ ΥΠΟΘΕΣΕΩΝ
103135	ΑΝΤΙΠΡΟΕΔΡΟΣ	ΝΟΜΙΚΟΥ ΣΥΜΒΟΥΛΙΟΥ ΤΟΥ ΚΡΑΤΟΥΣ

<signer>
<uid>103135</uid>
<firstName>ΑΝΤΙΠΡΟΕΔΡΟΣ</firstName>
<lastName>ΝΟΜΙΚΟΥ ΣΥΜΒΟΥΛΙΟΥ ΤΟΥ ΚΡΑΤΟΥΣ</lastName>
<active>true</active>
<activeFrom>2010-01-01T02:00:00+02:00</activeFrom>
<activeUntil>3000-01-01T00:00:00+02:00</activeUntil>
<organizationId>50024</organizationId>
<hasOrganizationSignRights>false</hasOrganizationSignRights>
<units>
<unit>
<positionId>POS_10026</positionId>
<positionLabel>Αντιπρόεδρος</positionLabel>
<uid>72922</uid>
</unit>
</units>
</signer>

<signer>
<uid>100031708</uid>
<firstName>ΠΡΟΪΣΤΑΜΕΝΟΣ ΔΙΕΥΘΥΝΣΗΣ</firstName>
<lastName>ΔΙΕΥΘΥΝΣΗ ΔΙΟΙΚΗΤΙΚΟΥ & ΛΕΙΤΟΥΡΓΙΚΗΣ ΥΠΟΣΤΗΡΙΞΗΣ</lastName>
<active>true</active>
<activeFrom>2017-06-14T03:00:00+03:00</activeFrom>
<activeUntil>3000-01-01T00:00:00.052+02:00</activeUntil>
<organizationId>50024</organizationId>
<hasOrganizationSignRights>false</hasOrganizationSignRights>
<units>
<unit>
<positionId>POS_10138</positionId>
<positionLabel>Προϊστάμενος Διεύθυνσης</positionLabel>
<uid>100031707</uid>
</unit>
</units>
</signer>

--------------------------------

Signers without any name at all:

https://diavgeia.gov.gr/opendata/signers/107914


<signer>
<uid>107914</uid>
<firstName/>
<lastName/>
<active>true</active>
<activeFrom>2010-01-01T02:00:00+02:00</activeFrom>
<activeUntil>3000-01-01T00:00:00+02:00</activeUntil>
<organizationId>50024</organizationId>
<hasOrganizationSignRights>false</hasOrganizationSignRights>
<units>
<unit>
<positionId>POS_10001</positionId>
<positionLabel>Υπουργός</positionLabel>
<uid>77199</uid>
</unit>
</units>
</signer>

--------------------------------

Same labels (expected to unique)

50063	katastima_kratisis_koridallou	Κ. Κ. Κ. I	ΥΠΟΥΡΓΕΙΟ ΔΗΜΟΣΙΑΣ ΤΑΞΗΣ ΚΑΙ  ΠΡΟΣΤΑΣΙΑΣ ΤΟΥ ΠΟΛΙΤΗ	active	OTHERTYPE	090169846	81	fektype_A	2019	http://www.mopocp.gov.gr		

54456	kkkorinthou	Σ. Κ. ΚΟΡΙΝΘΟΥ	ΥΠΟΥΡΓΕΙΟ ΔΗΜΟΣΙΑΣ ΤΑΞΗΣ ΚΑΙ  ΠΡΟΣΤΑΣΙΑΣ ΤΟΥ ΠΟΛΙΤΗ	active	OTHERTYPE	090169846	1	fektype_A	2000	http://kkkorinthou@otenet.gr		

99200516	gkkm	ΣΩΦΡΟΝΙΣΤΙΚΟ ΚΑΤΑΣΤΗΜΑ ΜΑΛΑΝΔΡΙΝΟΥ	ΥΠΟΥΡΓΕΙΟ ΔΗΜΟΣΙΑΣ ΤΑΞΗΣ ΚΑΙ  ΠΡΟΣΤΑΣΙΑΣ ΤΟΥ ΠΟΛΙΤΗ	active	OTHERTYPE	090169846	119	fektype_A	2019			

99200384	kassaveteia	ΕΑΣΚΝ ΚΑΣΣΑΒΕΤΕΙΑΣ	ΥΠΟΥΡΓΕΙΟ ΔΗΜΟΣΙΑΣ ΤΑΞΗΣ ΚΑΙ  ΠΡΟΣΤΑΣΙΑΣ ΤΟΥ ΠΟΛΙΤΗ	active	OTHERTYPE	090169846	119	fektype_A	2019			

--------------------------------

AFM - I'd expect them to be 9 digits

There's only X:

https://diavgeia.gov.gr/opendata/organizations/52760

<organization>
<uid>52760</uid>
<label>ΣΧΟΛΙΚΗ ΕΠΙΤΡΟΠΗ Α/ΘΜΙΑΣ ΕΚΠΑΙΔΕΥΣΗΣ ΔΗΜΟΥ ΛΑΜΙΕΩΝ</label>
<latinName>protovathmia-sxol-epitropi</latinName>
<status>active</status>
<category>NPDD</category>
<vatNumber>xxxxxxxxxxxx</vatNumber>
<fekNumber>0</fekNumber>
<fekIssue/>
<fekYear>0</fekYear>
<odeManagerEmail>info@lamia-city.gr</odeManagerEmail>
<website>http://www.lamia-city.gr</website>
<supervisorId>6166</supervisorId>
<supervisorLabel>ΔΗΜΟΣ ΛΑΜΙΕΩΝ</supervisorLabel>
<organizationDomains/>
</organization>

Fewer digits:

<organization xmlns="http://diavgeia.gov.gr/schema/v2">
<uid>50204</uid>
<label>ΑΠΟΚΕΝΤΡΩΜΕΝΗ ΔΙΟΙΚΗΣΗ ΚΡΗΤΗΣ</label>
<latinName>apdik_krhths</latinName>
<status>active</status>
<category>ADMINISTRATIVEREGION</category>
<vatNumber>50204</vatNumber>
<fekNumber>0</fekNumber>
<fekIssue/>
<fekYear>0</fekYear>
<odeManagerEmail>g.karamanolis@gmail.com</odeManagerEmail>
<website>http://50204</website>
<supervisorId>22887</supervisorId>
<supervisorLabel>ΠΕΡΙΦΕΡΕΙΕΣ</supervisorLabel>
<organizationDomains/>
</organization>

Or totally empty:

<organization xmlns="http://diavgeia.gov.gr/schema/v2">
<uid>50012</uid>
<label>ΗΛΕΚΤΡΙΚΟΙ ΣΙΔΗΡΟΔΡΟΜΟΙ ΑΘΗΝΩΝ ΠΕΙΡΑΙΩΣ Α.Ε.</label>
<latinName>isap</latinName>
<status>active</status>
<category>OTHERTYPE</category>
<vatNumber/>
<fekNumber>0</fekNumber>
<fekIssue/>
<fekYear>0</fekYear>
<odeManagerEmail>pro@isap.gr</odeManagerEmail>
<website/>
<supervisorId>100025905</supervisorId>
<supervisorLabel>ΥΠΟΥΡΓΕΙΟ ΥΠΟΔΟΜΩΝ ΚΑΙ ΜΕΤΑΦΟΡΩΝ</supervisorLabel>
<organizationDomains/>
</organization>

--------------------------------

### 🔬 **ROOT CAUSE ANALYSIS: Why Time Components Break Everything**

**The Smoking Gun**: Look at the actual queries being generated in the response `<query>` field.

#### ✅ **Date-Only Query (Works)**:
```
https://diavgeia.gov.gr/opendata/search?from_issue_date=2025-04-29&to_issue_date=2025-04-29&size=1
```
**Generated Query**:
```xml
<query>submissionTimestamp:[DT(2025-04-29T00:00:00+03:00) TO DT(2025-05-29T12:03:54+03:00)] 
AND issueDate:[DT(2025-04-29T00:00:00+03:00) TO DT(2025-04-29T00:00:00+03:00)] 
AND status:"Αναρτημένη"</query>
```
✅ **Correct**: Uses both `issueDate` (your target date) AND `submissionTimestamp` filters

#### ❌ **Time-Based Query (Broken)**:
```
https://diavgeia.gov.gr/opendata/search?from_issue_date=2025-04-29T00:00:00&to_issue_date=2025-04-29T01:00:00&size=1
```
**Generated Query**:
```xml
<query>submissionTimestamp:[DT(2024-11-30T12:04:34+02:00) TO DT(2025-05-29T12:04:34+03:00)]</query>
```
❌ **BROKEN**: 
- **MISSING** `issueDate` filter completely!
- **WRONG** `submissionTimestamp` range (6 months ago to now)
- **IGNORES** your specified dates entirely

### 🎯 **The Bug Explained**

When time components (`T00:00:00`) are present:
1. API **discards** your `from_issue_date`/`to_issue_date` parameters
2. API **converts** them to a `submissionTimestamp` range instead
3. API **uses current time ± 6 months** instead of your dates
4. API **removes** the `issueDate` filter completely
5. Result: **All decisions submitted in the last 6 months** (~3M decisions)

### 📊 **Evidence Table**

| Query Type | issueDate Filter | submissionTimestamp Filter | Result Count | Status |
|------------|------------------|----------------------------|--------------|---------|
| Date-only  | ✅ Uses your date | ✅ Reasonable range | ~1,500 | ✅ Works |
| Time-based | ❌ **MISSING**   | ❌ 6-month window   | ~3,000,000 | ❌ Broken |

### 🔧 **Technical Details**

**From API Documentation** (`/search/terms/common`):
- `submissionTimestamp`: "Ημ/νία ανάρτησης" (Submission/Publication Date)
- This is **different** from `issueDate` (Decision Issue Date)

**The API Bug**: Time components cause incorrect parameter mapping:
- `from_issue_date=2025-04-29T00:00:00` → `submissionTimestamp` filter (WRONG!)
- `from_issue_date=2025-04-29` → `issueDate` filter (CORRECT!)

### 💡 **Why This Matters**

- **issueDate**: When the decision was officially made
- **submissionTimestamp**: When it was uploaded to the system
- These can be **days or weeks apart**
- Searching by submission date returns the wrong decisions!

--------------------------------

## 🔥 **FINAL PROOF: The API is Fundamentally Broken**

### **Live Rolling Window Bug**

**Repeating the SAME query returns DIFFERENT totals:**
- Query: `https://diavgeia.gov.gr/opendata/search?from_submission_timestamp=2025-04-29&size=1`
- **12:28:23**: `<total>3000112</total>`
- **12:30:xx**: `<total>3000472</total>`
- **12:32:xx**: `<total>3000xxx</total>` (changes randomly)

**This proves the API returns a 6-month rolling window of current data, NOT your query results!**

### **Official API Parameters (Confirmed)**

From `https://diavgeia.gov.gr/opendata/search/terms/common`:

| Parameter | Greek Label | English Translation | Status |
|-----------|-------------|-------------------|---------|
| `issueDate` | Ημ/νία έκδοσης | Issue Date | ✅ Works (date-only) |
| `submissionTimestamp` | Ημ/νία τελευταίας τροποποίησης | Last Modification Date | ❌ Broken for time ranges |

### **Definitive Conclusion**

**The Diavgeia API cannot:**
- ❌ Filter by hour/minute ranges
- ❌ Query submission timestamps with time precision  
- ❌ Support distributed processing by time
- ❌ Provide consistent results for time-based queries

**The API only supports:**
- ✅ Date-only issue date filtering (`from_issue_date=2025-04-29`)
- ✅ Basic pagination within date ranges
- ✅ Organization/signer/type filtering

### **Business Impact: HOURLY DISTRIBUTION IS IMPOSSIBLE**

Any attempt to:
- Split workload by hour → **Returns entire database**
- Query recent submissions → **Returns 6-month window**  
- Use time-based pagination → **Completely broken**

**Recommendation**: Abandon time-based distribution strategies. Use date-only processing with alternative distribution methods (organization, type, etc.).



------------

Year is 20254

https://diavgeia.gov.gr/opendata/organizations/6020/signers

This XML file does not appear to have any style information associated with it. The document tree is shown below.
<signers xmlns="http://diavgeia.gov.gr/schema/v2">
<signer>
<uid>100084426</uid>
<firstName>ΓΕΩΡΓΙΟΣ</firstName>
<lastName>ΑΡΑΠΙΤΣΑΣ</lastName>
<active>true</active>
<activeFrom>2024-01-02T02:00:00+02:00</activeFrom>
<organizationId>6020</organizationId>
<hasOrganizationSignRights>true</hasOrganizationSignRights>
<units>
<unit>
<positionId>POS_10091</positionId>
<positionLabel>Δήμαρχος</positionLabel>
<uid>6020</uid>
</unit>
</units>
</signer>
<signer>
...
<signer>
<uid>100011585</uid>
<firstName>ΔΗΜΗΤΡΙΟΣ</firstName>
<lastName>ΠΑΛΙΟΓΙΑΝΝΗΣ</lastName>
<active>true</active>
<activeFrom>2015-06-11T03:00:00+03:00</activeFrom>

<activeUntil>20254-01-01T02:00:00+02:00</activeUntil>

<organizationId>6020</organizationId>
<hasOrganizationSignRights>false</hasOrganizationSignRights>
<units>
<unit>
...
</signers>