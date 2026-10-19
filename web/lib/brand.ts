// Data copied from dashboard/brand.py (generated from the Python values, not retyped).

/** key -> [display name, short] */
export const SOURCE_NAMES: Record<string, [string, string]> = {
  "asa": [
    "Advertising Standards Authority",
    "ASA"
  ],
  "bgc": [
    "Betting and Gaming Council",
    "BGC"
  ],
  "companies_house": [
    "Companies House",
    "CH"
  ],
  "dcms": [
    "DCMS",
    "DCMS"
  ],
  "gambling_commission": [
    "Gambling Commission",
    "GC"
  ],
  "gazette": [
    "The Gazette",
    "TG"
  ],
  "lse_rns": [
    "LSE RNS",
    "RNS"
  ],
  "parliament": [
    "UK Parliament",
    "UKP"
  ]
};

export const SOURCE_DOMAINS: Record<string, string> = {
  "asa": "asa.org.uk",
  "bgc": "bettingandgamingcouncil.com",
  "companies_house": "companieshouse.gov.uk",
  "dcms": "gov.uk",
  "gambling_commission": "gamblingcommission.gov.uk",
  "gazette": "thegazette.co.uk",
  "lse_rns": "lseg.com",
  "parliament": "parliament.uk"
};

export const COMPANY_DOMAINS: Record<string, string> = {
  "Allwyn": "allwyn.co.uk",
  "bet365": "bet365.com",
  "bet365 Group": "bet365.com",
  "Betfair": "betfair.com",
  "Checkout": "checkout.com",
  "Checkout Ltd": "checkout.com",
  "ClearBank": "clear.bank",
  "Coral": "coral.co.uk",
  "Entain": "entaingroup.com",
  "Entain Holdings (UK)": "entaingroup.com",
  "evoke": "evokeplc.com",
  "Evolution": "evolution.com",
  "Evolution Malta": "evolution.com",
  "Evolution Malta Holding": "evolution.com",
  "Flutter": "flutter.com",
  "Flutter Entertainment": "flutter.com",
  "GoCardless": "gocardless.com",
  "Grosvenor Casinos": "grosvenorcasinos.com",
  "Klarna": "klarna.com",
  "Klarna Financial Services UK": "klarna.com",
  "Ladbrokes": "ladbrokes.com",
  "Ladbrokes Coral Group": "ladbrokes.com",
  "Ministry of Housing, Communities and Local Government": "gov.uk",
  "Monzo": "monzo.com",
  "Monzo Bank": "monzo.com",
  "Revolut": "revolut.com",
  "Starling": "starlingbank.com",
  "Starling Bank": "starlingbank.com",
  "Wise": "wise.com",
  "Wise Payments": "wise.com",
  "Gambling Commission": "gamblingcommission.gov.uk",
  "Betting and Gaming Council": "bettingandgamingcouncil.com",
  "BGC": "bettingandgamingcouncil.com",
  "Advertising Standards Authority": "asa.org.uk",
  "ASA": "asa.org.uk",
  "Department for Culture, Media and Sport": "gov.uk",
  "DCMS": "gov.uk",
  "QuinnBet": "quinnbet.com",
  "Rank": "rank.com",
  "Rank Group": "rank.com",
  "William Hill": "williamhill.com"
};

export const PEOPLE: Set<string> = new Set([
  "Abouleyazid Mustafa Lubna",
  "Alexandra Butler",
  "Ann Allen",
  "Annie Hampson",
  "Anthony Francis Lane",
  "Anya Hurlbert",
  "Ayeni Ibukun Samson",
  "Baroness Morgan",
  "Clare Anderson",
  "Edgar Wright",
  "Elizabeth Karlsen",
  "Ganan Kanagathurai",
  "Hakan Kousetta",
  "Helen Williams",
  "James Twining",
  "Jane Tranter",
  "Janice Lane",
  "John Healey",
  "Judith Donovan",
  "Katie Town",
  "Lance Batchelor",
  "Laura Miele",
  "Lisa Nandy",
  "Louie French",
  "Mark Herbert",
  "Marshall Manson",
  "Maxwell Taylor",
  "Monica Chadha",
  "Mukesh Sharma",
  "Pamela Taylor",
  "Priya Guha",
  "Rachel Reeves",
  "Rebecca Crook",
  "Rhodri Lewis",
  "Richard Harris",
  "Rosalind Polly Blakesley",
  "Ruth Evans",
  "Ryan Prince",
  "Sanjeev Gupta",
  "Sarah Fox",
  "Sarah Gardner",
  "Simon Cox",
  "Song Liang",
  "Stephen Deuchar",
  "Stephen Dimmick",
  "Sue Young",
  "Tanya Cordrey",
  "Tim Miller",
  "Tom Solomon",
  "Toufic Machnouk",
  "Vicky Foxcroft",
  "Zura Adam Galgerud"
]);

/** Real logo files served from /public, by source key. */
export const SOURCE_LOGOS: Record<string, string> = { gambling_commission: "/logos/gambling_commission.png" };

export const ICON_PATHS: Record<string, { d: string; viewBox: string }> = {
  "trending_up": {
    "d": "m123-240-43-43 292-291 167 167 241-241H653v-60h227v227h-59v-123L538-321 371-488 123-240Z",
    "viewBox": "0 -960 960 960"
  },
  "trending_down": {
    "d": "M653-240v-60h127L539-541 372-374 80-665l43-43 248 248 167-167 283 283v-123h59v227H653Z",
    "viewBox": "0 -960 960 960"
  },
  "trending_flat": {
    "d": "m702-301-43-42 106-106H120v-60h646L660-615l42-42 178 178-178 178Z",
    "viewBox": "0 -960 960 960"
  },
  "account_balance": {
    "d": "M212-241v-339h60v339h-60Zm242 0v-339h60v339h-60ZM80-121v-60h800v60H80Zm608-120v-339h60v339h-60ZM80-640v-53l400-228 400 228v53H80Zm134-60h532-532Zm0 0h532L480-852 214-700Z",
    "viewBox": "0 -960 960 960"
  },
  "block": {
    "d": "M324-111.5Q251-143 197-197t-85.5-127Q80-397 80-480t31.5-156Q143-709 197-763t127-85.5Q397-880 480-880t156 31.5Q709-817 763-763t85.5 127Q880-563 880-480t-31.5 156Q817-251 763-197t-127 85.5Q563-80 480-80t-156-31.5ZM480-140q61.01 0 117.51-20.5Q654-181 699-220L220-699q-38 46-59 102.17T140-480q0 142.37 98.81 241.19Q337.63-140 480-140Zm259-121q37-45 59-101.49 22-56.5 22-117.51 0-142.38-98.81-241.19T480-820q-60.66 0-116.83 21T261-739l478 478ZM480-480Z",
    "viewBox": "0 -960 960 960"
  },
  "campaign": {
    "d": "M730-450v-60h150v60H730Zm50 290-121-90 36-48 121 90-36 48Zm-82-503-36-48 118-89 36 48-118 89ZM210-200v-160H80v-240h240l200-120v480L320-360h-50v160h-60Zm250-146v-268l-124 74H140v120h196l124 74Zm100 0v-268q27 24 43.5 58.5T620-480q0 41-16.5 75.5T560-346ZM300-480Z",
    "viewBox": "0 -960 960 960"
  },
  "description": {
    "d": "M319-250h322v-60H319v60Zm0-170h322v-60H319v60ZM160-80v-800h421l219 219v581H160Zm391-554v-186H220v680h520v-494H551ZM220-820v186-186 680-680Z",
    "viewBox": "0 -960 960 960"
  },
  "forum": {
    "d": "M240-240v-140h500v-340h140v639L721-240H240ZM80-280v-600h600v440H240L80-280Zm60-145 75-75h405v-320H140v395Zm0-75v-320 320Z",
    "viewBox": "0 -960 960 960"
  },
  "groups": {
    "d": "M0-240v-53q0-38.57 41.5-62.78Q83-380 150.38-380q12.16 0 23.39.5t22.23 2.15q-8 17.35-12 35.17-4 17.81-4 37.18v65H0Zm240 0v-65q0-32 17.5-58.5T307-410q32-20 76.5-30t96.5-10q53 0 97.5 10t76.5 30q32 20 49 46.5t17 58.5v65H240Zm540 0v-65q0-19.86-3.5-37.43T765-377.27q11-1.73 22.17-2.23 11.17-.5 22.83-.5 67.5 0 108.75 23.77T960-293v53H780Zm-480-60h360v-6q0-37-50.5-60.5T480-390q-79 0-129.5 23.5T300-305v5ZM149.57-410q-28.57 0-49.07-20.56Q80-451.13 80-480q0-29 20.56-49.5Q121.13-550 150-550q29 0 49.5 20.5t20.5 49.93q0 28.57-20.5 49.07T149.57-410Zm660 0q-28.57 0-49.07-20.56Q740-451.13 740-480q0-29 20.56-49.5Q781.13-550 810-550q29 0 49.5 20.5t20.5 49.93q0 28.57-20.5 49.07T809.57-410ZM480-480q-50 0-85-35t-35-85q0-51 35-85.5t85-34.5q51 0 85.5 34.5T600-600q0 50-34.5 85T480-480Zm.35-60Q506-540 523-557.35t17-43Q540-626 522.85-643t-42.5-17q-25.35 0-42.85 17.15t-17.5 42.5q0 25.35 17.35 42.85t43 17.5ZM480-300Zm0-300Z",
    "viewBox": "0 -960 960 960"
  },
  "handshake": {
    "d": "M474-40 93-421l303-303 146 146 42-42-240-240L41-557l73 73-42 42-116-116 387-387 124 124 124-124 394 394L474-40Zm1-84 425-427-309-309-81 81 159 159-127 127-146-146-218 218 42 42 163-163 43 43-163 163 43 43 163-163 42 42-163 163 41 41 163-163 43 43-163 163 43 43ZM362-651Z",
    "viewBox": "0 -960 960 960"
  },
  "health_and_safety": {
    "d": "M440-360h80v-100h100v-80H520v-100h-80v100H340v80h100v100Zm40 279q-140-35-230-162.5T160-523v-238l320-120 320 120v238q0 152-90 279.5T480-81Zm0-62q115-38 187.5-143.5T740-523v-196l-260-98-260 98v196q0 131 72.5 236.5T480-143Zm0-337Z",
    "viewBox": "0 -960 960 960"
  },
  "label": {
    "d": "M80-160v-640h561l240 320-239 320H80Zm60-60h471l195-260-195-260H140v520Zm333-260Z",
    "viewBox": "0 -960 960 960"
  },
  "money_off": {
    "d": "M577-623q-14-34-40-53t-62-19q-31 0-55 10.5T379-654l-42-42q21-24 48.5-38t58.5-18v-88h60v87q42 5 76.5 30.5T635-649l-58 26ZM806-56 614-248q-22 21-50.5 31T504-205v85h-60v-86q-57-8-95-45.5T295-343l60-21q14 51 45.5 76t79.5 25q26 0 50.5-6.5T570-292L57-805l43-43L849-99l-43 43Z",
    "viewBox": "0 -960 960 960"
  },
  "person": {
    "d": "M372-523q-42-42-42-108t42-108q42-42 108-42t108 42q42 42 42 108t-42 108q-42 42-108 42t-108-42ZM160-160v-94q0-38 19-65t49-41q67-30 128.5-45T480-420q62 0 123 15.5T731-360q31 14 50 41t19 65v94H160Zm60-60h520v-34q0-16-9.5-30.5T707-306q-64-31-117-42.5T480-360q-57 0-111 11.5T252-306q-14 7-23 21.5t-9 30.5v34Zm324.5-346.5Q570-592 570-631t-25.5-64.5Q519-721 480-721t-64.5 25.5Q390-670 390-631t25.5 64.5Q441-541 480-541t64.5-25.5ZM480-631Zm0 411Z",
    "viewBox": "0 -960 960 960"
  },
  "pie_chart": {
    "d": "M510-510h309q-11-122-98.5-211.5T510-819v309Zm-60 369v-678q-131 11-220.5 109T140-480q0 132 89.5 230T450-141Zm60 0q123-8 210.5-97.5T819-450H510v309Zm-30-339Zm0 400q-83 0-156-31.5T197-197q-54-54-85.5-127T80-480q0-83 31.5-156T197-763q54-54 127-85.5T480-880q83 0 156 31.5T763-763q54 54 85.5 127T880-480q0 83-31.5 156T763-197q-54 54-127 85.5T480-80Z",
    "viewBox": "0 -960 960 960"
  },
  "policy": {
    "d": "M480-80q-140-35-230-162.5T160-522v-238l320-120 320 120v238q0 78-21.5 154.5T703-225L563-359q-19 11-40.16 18-21.16 7-42.84 7-62 0-105.5-43T331-482.5q0-62.5 43.5-106T480-632q62 0 105.5 43.5T629-482q0 21-6 42t-19 38l88 84q24-43 36-96.5T740-522v-198.48L480-815l-260 94.52V-522q0 131 72.5 236.5T480.2-142q28.8-8 70.3-33t65.5-48l42 43q-35 32-83.5 60.5T480-80Zm63-339.5q26-25.5 26-63T542.8-546q-26.21-26-63-26-36.8 0-62.8 26t-26 63.5q0 37.5 26.2 63 26.21 25.5 63 25.5 36.8 0 62.8-25.5ZM479-484Z",
    "viewBox": "0 -960 960 960"
  },
  "receipt_long": {
    "d": "M222-80q-43.75 0-74.37-30.63Q117-141.25 117-185v-125h127v-570l59.8 60 59.8-60 59.8 60 59.8-60 59.8 60 60-60 60 60 60-60 60 60 60-60v695q0 43.75-30.62 74.37Q781.75-80 738-80H222Zm516-60q20 0 32.5-12.5T783-185v-595H304v470h389v125q0 20 12.5 32.5T738-140ZM357-622v-60h240v60H357Zm0 134v-60h240v60H357Zm333-134q-12 0-21-9t-9-21q0-12 9-21t21-9q12 0 21 9t9 21q0 12-9 21t-21 9Zm0 129q-12 0-21-9t-9-21q0-12 9-21t21-9q12 0 21 9t9 21q0 12-9 21t-21 9ZM221-140h412v-110H177v65q0 20 12.65 32.5T221-140Zm-44 0v-110 110Z",
    "viewBox": "0 -960 960 960"
  },
  "request_quote": {
    "d": "M450-201h60v-40h90v-190H420v-70h180v-60h-90v-40h-60v40h-90v190h180v70H360v60h90v40ZM160-80v-800h421l219 219v581H160Zm60-60h520v-494H554v-186H220v680Zm0-680v186-186 680-680Z",
    "viewBox": "0 -960 960 960"
  },
  "verified_user": {
    "d": "m436-347 228-228-42-41-183 183-101-101-44 44 142 143Zm44 266q-140-35-230-162.5T160-523v-238l320-120 320 120v238q0 152-90 279.5T480-81Zm0-62q115-38 187.5-143.5T740-523v-196l-260-98-260 98v196q0 131 72.5 236.5T480-143Zm0-337Z",
    "viewBox": "0 -960 960 960"
  },
  "gavel": {
    "d": "M3.33496 17.4984V15.8317H13.335V17.4984H3.33496ZM8.04329 13.4567L3.33496 8.74837L5.08496 6.95671L9.83496 11.665L8.04329 13.4567ZM13.335 8.16504L8.62663 3.41504L10.4183 1.66504L15.1266 6.37337L13.335 8.16504ZM17.1683 16.665L6.29329 5.79004L7.45996 4.62337L18.335 15.4984L17.1683 16.665Z",
    "viewBox": "0 0 20 20"
  },
  "corporate_fare": {
    "d": "M1.66667 17.5V2.5H10V5.83333H18.3333V17.5H1.66667ZM3.33333 15.8333H8.33333V14.1667H3.33333V15.8333ZM3.33333 12.5H8.33333V10.8333H3.33333V12.5ZM3.33333 9.16667H8.33333V7.5H3.33333V9.16667ZM3.33333 5.83333H8.33333V4.16667H3.33333V5.83333ZM10 15.8333H16.6667V7.5H10V15.8333ZM11.6667 10.8333V9.16667H15V10.8333H11.6667ZM11.6667 14.1667V12.5H15V14.1667H11.6667Z",
    "viewBox": "0 0 20 20"
  },
  "link": {
    "d": "M5.3 14C4.38889 14 3.61111 13.6778 2.96667 13.0333C2.32222 12.3889 2 11.6111 2 10.7C2 10.2556 2.08333 9.83333 2.25 9.43333C2.41667 9.03333 2.65556 8.67778 2.96667 8.36667L5.2 6.15L6.13333 7.08333L3.9 9.31667C3.71111 9.50556 3.56956 9.71956 3.47533 9.95867C3.38111 10.1978 3.33378 10.4449 3.33333 10.7C3.33333 11.2444 3.52511 11.7084 3.90867 12.092C4.29222 12.4756 4.756 12.6671 5.3 12.6667C5.55556 12.6667 5.80556 12.6193 6.05 12.5247C6.29444 12.43 6.51111 12.2884 6.7 12.1L8.91667 9.86667L9.86667 10.8167L7.63333 13.0333C7.32222 13.3444 6.96667 13.5833 6.56667 13.75C6.16667 13.9167 5.74444 14 5.3 14ZM6.61667 10.3333L5.66667 9.38333L9.38333 5.66667L10.3333 6.61667L6.61667 10.3333ZM10.8 9.86667L9.86667 8.91667L12.1 6.7C12.2889 6.51111 12.4278 6.3 12.5167 6.06667C12.6056 5.83333 12.65 5.58889 12.65 5.33333C12.65 4.77778 12.4611 4.30556 12.0833 3.91667C11.7056 3.52778 11.2389 3.33333 10.6833 3.33333C10.4278 3.33333 10.1807 3.38067 9.942 3.47533C9.70333 3.57 9.48933 3.71156 9.3 3.9L7.08333 6.13333L6.13333 5.2L8.36667 2.96667C8.67778 2.65556 9.03333 2.41667 9.43333 2.25C9.83333 2.08333 10.2556 2 10.7 2C11.6111 2 12.386 2.32222 13.0247 2.96667C13.6633 3.61111 13.9829 4.39444 13.9833 5.31667C13.9833 5.75 13.9027 6.16667 13.7413 6.56667C13.58 6.96667 13.344 7.32222 13.0333 7.63333L10.8 9.86667Z",
    "viewBox": "0 0 16 16"
  }
};

const CATEGORY_ICON_NAMES: Record<string, string> = {
  "AML and compliance failures": "policy",
  "Advertising ruling": "campaign",
  "Board and director changes": "groups",
  "Consultation": "forum",
  "Corporate filing": "description",
  "Director disqualification": "person",
  "Enforcement action": "gavel",
  "Financial results": "receipt_long",
  "Illegal gambling": "block",
  "Insolvency": "money_off",
  "Licence action": "verified_user",
  "Merger and acquisition": "handshake",
  "Player protection": "health_and_safety",
  "Policy and legislation": "account_balance",
  "Shareholding disclosure": "pie_chart",
  "Tax and levy": "request_quote",
  "Other": "label"
};

/** Icon key for a category; unknown or empty falls back to "label" (Python: .get(category or "", "label")). */
export function categoryIconName(category: string | null | undefined): string {
  return CATEGORY_ICON_NAMES[category || ""] ?? "label";
}
