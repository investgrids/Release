## Global invariants (18 questions)

| ID | UI mode same | entities same | Gate A same | would-call same | events b>a | news b>a | ann b>a | dups b>a | median age b>a (d) | admin items b>a | topical-tag items b>a |
|---|---|---|---|---|---|---|---|---|---|---|---|
| CR1 | yes | yes | yes | yes | 0>0 | 0>0 | 4>2 | 2>0 | 48.5>45.7 | 2>1 | 0>0 |
| CR2 | yes | yes | yes | yes | 0>0 | 0>0 | 0>0 | 0>0 | None>None | 0>0 | 0>0 |
| CR3 | yes | yes | yes | yes | 1>1 | 0>1 | 2>2 | 0>0 | 4.2>4.2 | 1>1 | 0>2 |
| EI1 | yes | yes | yes | yes | 0>0 | 0>0 | 0>0 | 0>0 | None>None | 0>0 | 0>0 |
| EI2 | yes | yes | yes | yes | 0>0 | 0>1 | 2>2 | 0>0 | 4.2>4.2 | 1>1 | 0>2 |
| EI3 | yes | yes | yes | yes | 8>10 | 11>10 | 0>0 | 0>0 | 0.0>1.0 | 1>0 | 5>10 |
| SR1 | yes | yes | yes | yes | 8>10 | 11>10 | 0>0 | 0>0 | 0.0>1.8 | 1>0 | 5>9 |
| SR2 | yes | yes | yes | yes | 8>10 | 2>5 | 0>0 | 0>0 | 3.7>3.6 | 0>0 | 16>22 |
| SR3 | yes | yes | yes | yes | 0>0 | 0>0 | 0>0 | 0>0 | None>None | 0>0 | 0>0 |
| MP1 | yes | yes | yes | yes | 8>10 | 12>10 | 0>0 | 0>0 | 0.0>0.9 | 0>0 | 7>17 |
| MP2 | yes | yes | yes | yes | 10>10 | 2>2 | 0>0 | 1>0 | 30.9>33.5 | 0>0 | 8>8 |
| MP3 | yes | yes | yes | yes | 10>10 | 5>8 | 0>0 | 0>0 | 2.0>1.9 | 0>0 | 15>20 |
| CC1 | yes | yes | yes | yes | 1>1 | 0>1 | 6>6 | 0>0 | 34.2>19.2 | 1>1 | 0>2 |
| CC2 | yes | yes | yes | yes | 0>0 | 2>7 | 6>6 | 0>0 | 34.2>0.0 | 1>1 | 1>3 |
| CC3 | yes | yes | yes | yes | 1>1 | 0>0 | 2>1 | 1>0 | 48.2>68.0 | 2>1 | 0>0 |
| GE1 | yes | yes | yes | yes | 0>0 | 0>0 | 0>0 | 0>0 | None>None | 0>0 | 0>0 |
| GE2 | yes | yes | yes | yes | 0>0 | 0>0 | 0>0 | 0>0 | None>None | 0>0 | 0>0 |
| GE3 | yes | yes | yes | yes | 0>0 | 0>0 | 0>0 | 0>0 | None>None | 0>0 | 0>0 |

Route unchanged for all 18: **True**. Entities unchanged: **True**. Gate A decision unchanged: **True**. Model-call population unchanged: **True**.

## Selected-evidence deltas per question (items in only one snapshot)

**CR1** (What is the outlook for Kotak Mahindra Bank?)
  - OUT announcement: 'Kotak Mahindra Bank Limited has informed the Exchange about General Updates' tags=['administrative'] age=48.2d in_prompt=True
  - OUT announcement: 'Investor Presentation' tags=[] age=48.9d in_prompt=True
**CR3** (What is happening with TCS lately?)
  - IN  new: 'TCS, Infosys and other IT stocks in focus after Accenture Q4 revenue, outlook beat estim' tags=['operating_result', 'outlook_demand'] age=0.1d in_prompt=True
**EI2** (TCS just announced a new AI research center, what does this )
  - IN  new: 'TCS, Infosys and other IT stocks in focus after Accenture Q4 revenue, outlook beat estim' tags=['operating_result', 'outlook_demand'] age=0.1d in_prompt=True
**EI3** (Banking sector just reported stronger credit growth, what is)
  - OUT event: 'RBI Remains Cautious On Crypto, Backs Underlying Technology: Governor Sanjay Malhotra' tags=[] age=1.8d in_prompt=True
  - OUT event: 'Sebi proposes mandatory colour-coded Credit Risk-o-Meter for debt securities' tags=[] age=52.0d in_prompt=True
  - OUT event: 'RBI to close FCNR(B) swaps a month earlier due to gush' tags=[] age=51.0d in_prompt=True
  - OUT event: 'Disclosure under Regulation 30 of the SEBI (Listing Obligations and Disclosure Requireme' tags=[] age=53.5d in_prompt=True
  - OUT event: 'Rupee holds steady at 95.44 amidst RBI intervention' tags=[] age=52.1d in_prompt=True
  - OUT event: 'Rupee logs weekly decline, with RBI intervention curbing losses' tags=['outlook_demand'] age=51.8d in_prompt=True
  - OUT event: 'Rupee nudges up on RBI intervention; investors eye inflation data' tags=['rate_policy'] age=53.5d in_prompt=False
  - OUT event: 'Pursuant to the SEBI (Listing Obligations and Disclosure Requirements) Regulations, 2015' tags=['administrative'] age=1.6d in_prompt=False
  - IN  event: 'RBI rate hike expected in October? What it means for Sensex, Nifty | Experts decode' tags=['outlook_demand', 'rate_policy'] age=3.8d in_prompt=True
  - IN  event: 'Stocks to watch | LIC gets RBI approval to acquire up to 9.99% stake in ICICI Bank' tags=[] age=28.6d in_prompt=True
  - IN  event: "India lenders' dollar debt sales top $10 billion since RBI window, ICICI Bank beats peer" tags=[] age=41.7d in_prompt=True
  - IN  event: "HDFC Bank CEO Race Ends As Anup Bagchi's 3-Year Appointment Gets RBI Nod" tags=[] age=3.6d in_prompt=True
  - IN  event: 'RBI eases bank stake rules, allows one-time approval for MFs, insurers for holdings up t' tags=[] age=3.6d in_prompt=True
  - IN  event: 'RBI MPC may hike repo rate next week: Experts share the equity-debt strategy investors s' tags=['rate_policy'] age=2.0d in_prompt=True
  - IN  event: 'Four Indian private banks eye dollar debt before RBI swap window deadline, bankers say' tags=[] age=47.6d in_prompt=False
  - IN  event: 'RBI Officials Meet NBFC Heads; Focus On Draft Guidelines For Revolving Credit, Complianc' tags=[] age=48.9d in_prompt=False
  - IN  event: 'Global bond rout hoists benchmark Indian yield to mid-2024 high before RBI policy' tags=['rate_policy'] age=3.7d in_prompt=False
  - IN  event: "RBI bond sales, FX intervention help halve India's cash overhang" tags=[] age=12.6d in_prompt=False
  - OUT new: 'Q2 biz update, ₹17,500-crore fundraise plan drive Bajaj Finance 4% higher' tags=[] age=0.0d in_prompt=False
  - OUT new: 'Stock market today LIVE: Sensex up 500 points, Nifty up 150 points; HDFC Bank, RIL, Baja' tags=[] age=0.0d in_prompt=False
  - OUT new: 'Indian markets open higher amid positive global cues; PSU bank stocks lead - Telangana T' tags=[] age=0.0d in_prompt=False
  - OUT new: 'Sensex, Nifty trade flat; Dr Reddy’s tops gainers, Kotak Bank leads losses - BusinessLin' tags=[] age=0.0d in_prompt=False
  - OUT new: 'Zerodha now wants to enter investment banking space, seeks Sebi nod' tags=[] age=0.0d in_prompt=False
  - OUT new: "Sensex Today | Stock Market Live: Sensex, Nifty at day's low; VIX up 7%, BSE, Persistent" tags=[] age=0.0d in_prompt=False
  - OUT new: 'Kotak Mahindra Bank, HDFC Bank, DCX Systems, among buzzing stocks as SENSEX falls over 3' tags=['outlook_demand'] age=0.0d in_prompt=False
  - IN  new: 'Yes Bank shares rise 3% after Q2 business update shows loans surging 24% YoY, deposits u' tags=[] age=0.0d in_prompt=False
  - IN  new: "Kotak Mahindra Bank Primed For Next Leg Of Growth As Street Cheers Anup Saha's Elevation" tags=['outlook_demand'] age=0.0d in_prompt=False
  - IN  new: "Anup Bagchi's Appointment Removes Key Overhang For HDFC Bank Stock, Supports Re-Rating, " tags=[] age=0.0d in_prompt=False
  - IN  new: 'Sensex, Nifty opening: Will stock market rise ahead of RBI MPC? - India Today' tags=['rate_policy'] age=0.0d in_prompt=False
  - IN  new: "India's bond yield curve poised to flatten as RBI drains surplus cash" tags=['rate_policy'] age=0.0d in_prompt=False
  - IN  new: 'HDFC Bank: Anup Bagchi at helm lifts overhang; brokerages share outlook' tags=['outlook_demand'] age=0.0d in_prompt=False
**SR1** (How is the banking sector doing right now?)
  - OUT event: 'RBI Remains Cautious On Crypto, Backs Underlying Technology: Governor Sanjay Malhotra' tags=[] age=1.8d in_prompt=True
  - OUT event: 'Sebi proposes mandatory colour-coded Credit Risk-o-Meter for debt securities' tags=[] age=52.0d in_prompt=True
  - OUT event: 'RBI to close FCNR(B) swaps a month earlier due to gush' tags=[] age=51.0d in_prompt=True
  - OUT event: 'Disclosure under Regulation 30 of the SEBI (Listing Obligations and Disclosure Requireme' tags=[] age=53.5d in_prompt=True
  - OUT event: 'Rupee holds steady at 95.44 amidst RBI intervention' tags=[] age=52.1d in_prompt=True
  - OUT event: 'Rupee logs weekly decline, with RBI intervention curbing losses' tags=['outlook_demand'] age=51.8d in_prompt=True
  - OUT event: 'Rupee nudges up on RBI intervention; investors eye inflation data' tags=['rate_policy'] age=53.5d in_prompt=False
  - OUT event: 'Pursuant to the SEBI (Listing Obligations and Disclosure Requirements) Regulations, 2015' tags=['administrative'] age=1.6d in_prompt=False
  - IN  event: 'Stocks to watch | LIC gets RBI approval to acquire up to 9.99% stake in ICICI Bank' tags=[] age=28.6d in_prompt=True
  - IN  event: "India lenders' dollar debt sales top $10 billion since RBI window, ICICI Bank beats peer" tags=[] age=41.7d in_prompt=True
  - IN  event: "HDFC Bank CEO Race Ends As Anup Bagchi's 3-Year Appointment Gets RBI Nod" tags=[] age=3.6d in_prompt=True
  - IN  event: 'RBI eases bank stake rules, allows one-time approval for MFs, insurers for holdings up t' tags=[] age=3.6d in_prompt=True
  - IN  event: 'Four Indian private banks eye dollar debt before RBI swap window deadline, bankers say' tags=[] age=47.6d in_prompt=True
  - IN  event: 'RBI Officials Meet NBFC Heads; Focus On Draft Guidelines For Revolving Credit, Complianc' tags=[] age=48.9d in_prompt=True
  - IN  event: 'Global bond rout hoists benchmark Indian yield to mid-2024 high before RBI policy' tags=['rate_policy'] age=3.7d in_prompt=False
  - IN  event: 'RBI rate hike expected in October? What it means for Sensex, Nifty | Experts decode' tags=['outlook_demand', 'rate_policy'] age=3.8d in_prompt=False
  - IN  event: "RBI bond sales, FX intervention help halve India's cash overhang" tags=[] age=12.6d in_prompt=False
  - IN  event: 'RBI issues norms on capital requirements for market risk under Basel III for banks' tags=[] age=13.6d in_prompt=False
  - OUT new: 'Q2 biz update, ₹17,500-crore fundraise plan drive Bajaj Finance 4% higher' tags=[] age=0.0d in_prompt=False
  - OUT new: 'Stock market today LIVE: Sensex up 500 points, Nifty up 150 points; HDFC Bank, RIL, Baja' tags=[] age=0.0d in_prompt=False
  - OUT new: 'Indian markets open higher amid positive global cues; PSU bank stocks lead - Telangana T' tags=[] age=0.0d in_prompt=False
  - OUT new: 'Sensex, Nifty trade flat; Dr Reddy’s tops gainers, Kotak Bank leads losses - BusinessLin' tags=[] age=0.0d in_prompt=False
  - OUT new: 'Zerodha now wants to enter investment banking space, seeks Sebi nod' tags=[] age=0.0d in_prompt=False
  - OUT new: "Sensex Today | Stock Market Live: Sensex, Nifty at day's low; VIX up 7%, BSE, Persistent" tags=[] age=0.0d in_prompt=False
  - OUT new: 'Kotak Mahindra Bank, HDFC Bank, DCX Systems, among buzzing stocks as SENSEX falls over 3' tags=['outlook_demand'] age=0.0d in_prompt=False
  - IN  new: 'Yes Bank shares rise 3% after Q2 business update shows loans surging 24% YoY, deposits u' tags=[] age=0.0d in_prompt=False
  - IN  new: "Kotak Mahindra Bank Primed For Next Leg Of Growth As Street Cheers Anup Saha's Elevation" tags=['outlook_demand'] age=0.0d in_prompt=False
  - IN  new: "Anup Bagchi's Appointment Removes Key Overhang For HDFC Bank Stock, Supports Re-Rating, " tags=[] age=0.0d in_prompt=False
  - IN  new: 'Sensex, Nifty opening: Will stock market rise ahead of RBI MPC? - India Today' tags=['rate_policy'] age=0.0d in_prompt=False
  - IN  new: "India's bond yield curve poised to flatten as RBI drains surplus cash" tags=['rate_policy'] age=0.0d in_prompt=False
  - IN  new: 'HDFC Bank: Anup Bagchi at helm lifts overhang; brokerages share outlook' tags=['outlook_demand'] age=0.0d in_prompt=False
**SR2** (What is the outlook for the IT services sector?)
  - IN  event: 'Release:  HCLTech report reveals telecom leaders identify AI as top revenue driver, but ' tags=['operating_result'] age=48.6d in_prompt=False
  - IN  event: 'Stock Market Crash Live: Nifty Falls Below 24,200, Sensex Slumps Nearly 500 Points From ' tags=['outlook_demand'] age=41.9d in_prompt=False
  - IN  new: 'TCS, Infosys and other IT stocks in focus after Accenture Q4 revenue, outlook beat estim' tags=['operating_result', 'outlook_demand'] age=0.1d in_prompt=False
  - IN  new: "Wipro Share Price Live Updates: Wipro's Price Movement Today" tags=[] age=0.1d in_prompt=False
  - IN  new: 'Indian IT’s Q2 earnings dilemma deepens: More deals but weaker growth and falling pricin' tags=['operating_result', 'outlook_demand'] age=0.0d in_prompt=False
**MP1** (What happens to Indian banks if the RBI cuts the repo rate?)
  - OUT event: 'RBI Remains Cautious On Crypto, Backs Underlying Technology: Governor Sanjay Malhotra' tags=[] age=1.8d in_prompt=True
  - OUT event: 'Sebi proposes mandatory colour-coded Credit Risk-o-Meter for debt securities' tags=[] age=52.0d in_prompt=True
  - OUT event: 'RBI to close FCNR(B) swaps a month earlier due to gush' tags=[] age=51.0d in_prompt=True
  - OUT event: 'Disclosure under Regulation 30 of the SEBI (Listing Obligations and Disclosure Requireme' tags=[] age=53.5d in_prompt=True
  - OUT event: 'Rupee holds steady at 95.44 amidst RBI intervention' tags=[] age=52.1d in_prompt=True
  - OUT event: 'Rupee logs weekly decline, with RBI intervention curbing losses' tags=['outlook_demand'] age=51.8d in_prompt=False
  - OUT event: 'Federal Reserve announces the leadership and objectives of its task forces to advance th' tags=['rate_policy'] age=52.6d in_prompt=False
  - OUT event: 'Rupee nudges up on RBI intervention; investors eye inflation data' tags=['rate_policy'] age=53.5d in_prompt=False
  - IN  event: 'RBI MPC Meeting October 2026: Repo rate hike soon? Date, announcement time, members, mon' tags=['outlook_demand', 'rate_policy'] age=2.0d in_prompt=True
  - IN  event: 'RBI MPC may hike repo rate next week: Experts share the equity-debt strategy investors s' tags=['rate_policy'] age=2.0d in_prompt=True
  - IN  event: 'RBI rate hike expected in October? What it means for Sensex, Nifty | Experts decode' tags=['outlook_demand', 'rate_policy'] age=3.8d in_prompt=True
  - IN  event: 'WACR tops repo rate for first time in nearly 2 months' tags=['rate_policy'] age=12.1d in_prompt=True
  - IN  event: 'US Fed, Bank of Japan and others impact on Indian stock markets: Global rate hike cycle ' tags=['outlook_demand', 'rate_policy'] age=13.7d in_prompt=True
  - IN  event: 'RBI Rate Hike Bets Rise After US Fed Move: Why October Policy Is Now A Close Call' tags=['rate_policy'] age=16.7d in_prompt=False
  - IN  event: 'After Sept, bond yields to peak in Oct too? Experts decode future of Indian bond market;' tags=['rate_policy'] age=1.8d in_prompt=False
  - IN  event: 'Global bond rout hoists benchmark Indian yield to mid-2024 high before RBI policy' tags=['rate_policy'] age=3.7d in_prompt=False
  - IN  event: 'Stocks to watch | LIC gets RBI approval to acquire up to 9.99% stake in ICICI Bank' tags=[] age=28.6d in_prompt=False
  - IN  event: 'Fed hike, RBI moves hand India bonds a fifth weekly loss' tags=[] age=16.7d in_prompt=False
  - OUT new: 'Q2 biz update, ₹17,500-crore fundraise plan drive Bajaj Finance 4% higher' tags=[] age=0.0d in_prompt=True
  - OUT new: 'Stock market today LIVE: Sensex up 500 points, Nifty up 150 points; HDFC Bank, RIL, Baja' tags=[] age=0.0d in_prompt=True
  - OUT new: 'Indian markets open higher amid positive global cues; PSU bank stocks lead - Telangana T' tags=[] age=0.0d in_prompt=True
  - OUT new: 'Sensex, Nifty trade flat; Dr Reddy’s tops gainers, Kotak Bank leads losses - BusinessLin' tags=[] age=0.0d in_prompt=False
  - OUT new: 'Zerodha now wants to enter investment banking space, seeks Sebi nod' tags=[] age=0.0d in_prompt=False
  - OUT new: "Sensex Today | Stock Market Live: Sensex, Nifty at day's low; VIX up 7%, BSE, Persistent" tags=[] age=0.0d in_prompt=False
  - OUT new: 'Kotak Mahindra Bank, HDFC Bank, DCX Systems, among buzzing stocks as SENSEX falls over 3' tags=['outlook_demand'] age=0.0d in_prompt=False
  - IN  new: 'Yes Bank shares rise 3% after Q2 business update shows loans surging 24% YoY, deposits u' tags=[] age=0.0d in_prompt=True
  - IN  new: "Kotak Mahindra Bank Primed For Next Leg Of Growth As Street Cheers Anup Saha's Elevation" tags=['outlook_demand'] age=0.0d in_prompt=True
  - IN  new: "Anup Bagchi's Appointment Removes Key Overhang For HDFC Bank Stock, Supports Re-Rating, " tags=[] age=0.0d in_prompt=True
  - IN  new: 'Sensex, Nifty opening: Will stock market rise ahead of RBI MPC? - India Today' tags=['rate_policy'] age=0.0d in_prompt=False
  - IN  new: "India's bond yield curve poised to flatten as RBI drains surplus cash" tags=['rate_policy'] age=0.0d in_prompt=False
**MP2** (How would higher crude oil prices affect Indian markets?)
  - OUT event: 'Week Ahead On D-Street: US Fed Minutes, Crude Oil Prices, US-Iran Conflict To Drive Sens' tags=[] age=49.9d in_prompt=False
  - OUT event: 'How will Nifty, Sensex behave on Monday? US Fed rate hike bets, among 4 factors to drive' tags=['rate_policy'] age=28.6d in_prompt=True
  - IN  event: 'Rupee faces pressure as RBI defends 95.45 against dollar amid rising crude oil prices' tags=['outlook_demand'] age=49.1d in_prompt=True
  - IN  event: 'US-Iran war to crude oil prices: Top five triggers that may dictate the Indian stock mar' tags=[] age=50.1d in_prompt=True
**MP3** (How would a weaker rupee affect Indian IT exporters?)
  - OUT event: 'Rupee holds steady at 95.44 amidst RBI intervention' tags=[] age=52.1d in_prompt=True
  - OUT event: 'Rupee logs weekly decline, with RBI intervention curbing losses' tags=['outlook_demand'] age=51.8d in_prompt=True
  - OUT event: 'Rupee nudges up on RBI intervention; investors eye inflation data' tags=['rate_policy'] age=53.5d in_prompt=True
  - OUT event: "India's forex reserves fall $18.3 bn as RBI steps in to defend rupee" tags=['outlook_demand'] age=2.0d in_prompt=False
  - IN  event: 'Infosys, Wipro ADRs soar up to 8% as strong Accenture earnings forecast lifts mood' tags=['operating_result', 'outlook_demand'] age=3.7d in_prompt=True
  - IN  event: 'Nifty IT jumps 2%; Mphasis, Coforge, Infosys, TCS among top gainers - Reason behind the ' tags=['operating_result', 'outlook_demand'] age=3.8d in_prompt=True
  - IN  event: 'Rupee strengthens to 95.59 amid drop in oil prices &amp; RBI dollar sales' tags=[] age=12.1d in_prompt=False
  - IN  event: 'RBI intervention, dollar flows push Indian rupee to two-month peak' tags=[] age=33.8d in_prompt=False
  - IN  new: 'TCS, Infosys and other IT stocks in focus after Accenture Q4 revenue, outlook beat estim' tags=['operating_result', 'outlook_demand'] age=0.1d in_prompt=True
  - IN  new: 'Indian IT’s Q2 earnings dilemma deepens: More deals but weaker growth and falling pricin' tags=['operating_result', 'outlook_demand'] age=0.0d in_prompt=True
  - IN  new: "Wipro Share Price Live Updates: Wipro's Price Movement Today" tags=[] age=0.1d in_prompt=False
**CC1** (TCS vs Infosys, which is stronger?)
  - IN  new: 'TCS, Infosys and other IT stocks in focus after Accenture Q4 revenue, outlook beat estim' tags=['operating_result', 'outlook_demand'] age=0.1d in_prompt=True
**CC2** (Compare HDFC Bank and ICICI Bank.)
  - IN  new: 'HDFC Bank: Anup Bagchi at helm lifts overhang; brokerages share outlook' tags=['outlook_demand'] age=0.0d in_prompt=True
  - IN  new: "Anup Bagchi's Appointment Removes Key Overhang For HDFC Bank Stock, Supports Re-Rating, " tags=[] age=0.0d in_prompt=True
  - IN  new: 'HDFC Bank shares rise 2% after appointing Anup Bagchi as new CEO, Q2 biz update. Buy, se' tags=[] age=0.0d in_prompt=False
  - IN  new: "HDFC Bank shares rise 2% as Street cheers Anup Bagchi's appointment as CEO" tags=[] age=0.0d in_prompt=False
  - IN  new: 'Why is market rising today? Sensex rallies 700 points, Nifty above 22,600. 6 key factors' tags=['outlook_demand'] age=0.0d in_prompt=False
**CC3** (I hold BEL. Should I switch to HAL?)
  - OUT announcement: 'Addendum to the Notice of the 72nd Annual General Meeting of the Company scheduled to be' tags=['administrative'] age=48.2d in_prompt=True

## Order of what the model is shown (prompt-visible events/news/announcements, first 6 each)

**CR1**
- before events        visible=0/0: []
- before news          visible=0/0: []
- before announcements visible=4/4: ['Kotak Mahindra Bank Limited has informed the Exchange about General Up', 'Kotak Mahindra Bank Limited has informed the Exchange about General Up', 'Investor Presentation', 'Kotak Mahindra Bank Limited has informed the Exchange about Investor P']
- after  events        visible=0/0: []
- after  news          visible=0/0: []
- after  announcements visible=2/2: ['Kotak Mahindra Bank Limited has informed the Exchange about Investor P', 'Kotak Mahindra Bank Limited has informed the Exchange about General Up']

**SR2**
- before events        visible=6/8: ['TCS, Infosys, Wipro shares ahead of Q2 results: Explained | What Accen', 'IT Q2 Results Dates: When TCS, Infosys, Wipro, HCLTech, Tech Mahindra ', 'Accenture Shares Jump Record 22% On Earnings Boost; Infosys, Wipro ADR', 'Infosys, Wipro ADRs jump up to 10% after Accenture Q4 results beat Wal', 'Infosys, Wipro ADRs Spike Over 8% Pre-Market As Solid Accenture Earnin', 'Nifty IT crashes 11% in September: TCS, Infosys, Wipro among top loser']
- before news          visible=0/2: []
- before announcements visible=0/0: []
- after  events        visible=6/10: ['TCS, Infosys, Wipro shares ahead of Q2 results: Explained | What Accen', 'IT Q2 Results Dates: When TCS, Infosys, Wipro, HCLTech, Tech Mahindra ', 'Nifty IT crashes 11% in September: TCS, Infosys, Wipro among top loser', 'Infosys, Wipro ADRs soar up to 8% as strong Accenture earnings forecas', 'Nifty IT jumps 2%; Mphasis, Coforge, Infosys, TCS among top gainers - ', 'Accenture Shares Jump Record 22% On Earnings Boost; Infosys, Wipro ADR']
- after  news          visible=0/5: []
- after  announcements visible=0/0: []

**MP1**
- before events        visible=5/8: ['RBI Remains Cautious On Crypto, Backs Underlying Technology: Governor ', 'Sebi proposes mandatory colour-coded Credit Risk-o-Meter for debt secu', 'RBI to close FCNR(B) swaps a month earlier due to gush', 'Disclosure under Regulation 30 of the SEBI (Listing Obligations and Di', 'Rupee holds steady at 95.44 amidst RBI intervention']
- before news          visible=5/12: ['HDFC Bank, YES Bank, AU SFB: Bank stocks jump; Bank Nifty up over 1% -', 'Q2 biz update, ₹17,500-crore fundraise plan drive Bajaj Finance 4% hig', 'Stock market today LIVE: Sensex up 500 points, Nifty up 150 points; HD', 'RBI likely intervenes to support rupee, traders say', 'Indian markets open higher amid positive global cues; PSU bank stocks ']
- before announcements visible=0/0: []
- after  events        visible=5/10: ['RBI MPC Meeting October 2026: Repo rate hike soon? Date, announcement ', 'RBI MPC may hike repo rate next week: Experts share the equity-debt st', 'RBI rate hike expected in October? What it means for Sensex, Nifty | E', 'WACR tops repo rate for first time in nearly 2 months', 'US Fed, Bank of Japan and others impact on Indian stock markets: Globa']
- after  news          visible=5/10: ['Yes Bank shares rise 3% after Q2 business update shows loans surging 2', 'US Stock Market: Wall Street eyes jobs data as rate hike bets and tech', 'Kotak Mahindra Bank Primed For Next Leg Of Growth As Street Cheers Anu', "Anup Bagchi's Appointment Removes Key Overhang For HDFC Bank Stock, Su", 'RBI likely intervenes to support rupee, traders say']
- after  announcements visible=0/0: []

**CC2**
- before events        visible=0/0: []
- before news          visible=2/2: ['HDFC Bank, YES Bank, AU SFB: Bank stocks jump; Bank Nifty up over 1% -', 'Stock market today LIVE: Sensex up 500 points, Nifty up 150 points; HD']
- before announcements visible=6/6: ['HDFC Bank Limited has informed the Exchange about General Updates', 'ICICI Bank Limited has informed the Exchange about Disclosure under Re', 'ICICI Bank Limited has informed the Exchange regarding Allotment of 59', 'ICICI Bank Limited has informed the Exchange about Credit Rating', 'ICICI Bank Limited has informed the Exchange about disclosure under Re', 'ICICI Bank Limited has informed the Exchange regarding Allotment of 18']
- after  events        visible=0/0: []
- after  news          visible=4/7: ['HDFC Bank, YES Bank, AU SFB: Bank stocks jump; Bank Nifty up over 1% -', 'HDFC Bank: Anup Bagchi at helm lifts overhang; brokerages share outloo', "Anup Bagchi's Appointment Removes Key Overhang For HDFC Bank Stock, Su", 'Stock market today LIVE: Sensex up 500 points, Nifty up 150 points; HD']
- after  announcements visible=6/6: ['HDFC Bank Limited has informed the Exchange about General Updates', 'ICICI Bank Limited has informed the Exchange about Credit Rating', 'ICICI Bank Limited has informed the Exchange about Disclosure under Re', 'ICICI Bank Limited has informed the Exchange about disclosure under Re', 'ICICI Bank Limited has informed the Exchange regarding Allotment of 59', 'ICICI Bank Limited has informed the Exchange regarding Allotment of 18']

## Target specimens

| Q | item | before selected / visible | after selected / visible |
|---|---|---|---|
| SR2 | event: *crashes 11%* | yes (1) / visible | yes (1) / visible |
| SR2 | new: *reality check* | no | no |
| SR2 | new: *earnings dilemma* | no | yes (1) / not visible |
| SR2 | event: *Q2 Results Dates* | yes (1) / visible | yes (1) / visible |
| SR2 | new: *Accenture Q4 revenue, outlook* | no | yes (1) / not visible |
| MP1 | event: *MPC may hike* | no | yes (1) / visible |
| MP1 | event: *MPC Meeting October* | no | yes (1) / visible |
| MP1 | event: *bond yields* | no | yes (1) / not visible |
| MP1 | event: *Rate Hike Bets* | no | yes (1) / not visible |
| MP1 | new: *RBI MPC* | no | yes (1) / not visible |
| CR1 | announcement: *Investor Presentation* | yes (2) / visible | yes (1) / visible |
| CR1 | announcement: *General Updates* | yes (2) / visible | yes (1) / visible |

## Rank components of the top selected items (after)

**SR2**
- event        score 0.88 (coverage 1.00, recency 0.97, substance 0.90, impact 0.00)  "TCS, Infosys, Wipro shares ahead of Q2 results: Explained | What Accenture's str"
- event        score 0.88 (coverage 1.00, recency 0.97, substance 0.90, impact 0.00)  'IT Q2 Results Dates: When TCS, Infosys, Wipro, HCLTech, Tech Mahindra Will Repor'
- event        score 0.87 (coverage 1.00, recency 0.94, substance 0.90, impact 0.00)  'Nifty IT crashes 11% in September: TCS, Infosys, Wipro among top losers — Can Q2'
- event        score 0.87 (coverage 1.00, recency 0.94, substance 0.90, impact 0.00)  'Infosys, Wipro ADRs soar up to 8% as strong Accenture earnings forecast lifts mo'
- event        score 0.87 (coverage 1.00, recency 0.94, substance 0.90, impact 0.00)  'Nifty IT jumps 2%; Mphasis, Coforge, Infosys, TCS among top gainers - Reason beh'
- event        score 0.70 (coverage 0.67, recency 0.94, substance 0.90, impact 0.00)  'Accenture Shares Jump Record 22% On Earnings Boost; Infosys, Wipro ADRs Spike Up'
- new          score 0.96 (coverage 1.00, recency 1.00, substance 0.90, impact 0.75)  'TCS, Infosys and other IT stocks in focus after Accenture Q4 revenue, outlook be'
- new          score 0.64 (coverage 0.33, recency 1.00, substance 0.90, impact 0.85)  'Stock market outlook today, 5 Oct: Sensex, Nifty prediction - DJIA, S&P, NASDAQ,'
- new          score 0.57 (coverage 0.33, recency 0.98, substance 0.50, impact 0.85)  'Weekly Market Wrap: NIFTY50, SENSEX end lower as metal, IT indices fall 4%; Info'
- new          score 0.56 (coverage 0.33, recency 1.00, substance 0.50, impact 0.70)  "Wipro Share Price Live Updates: Wipro's Price Movement Today"
- new          score 0.54 (coverage 0.17, recency 1.00, substance 0.90, impact 0.75)  'Indian IT’s Q2 earnings dilemma deepens: More deals but weaker growth and fallin'

**MP1**
- event        score 0.88 (coverage 1.00, recency 0.97, substance 0.90, impact 0.00)  'RBI MPC Meeting October 2026: Repo rate hike soon? Date, announcement time, memb'
- event        score 0.88 (coverage 1.00, recency 0.97, substance 0.90, impact 0.00)  'RBI MPC may hike repo rate next week: Experts share the equity-debt strategy inv'
- event        score 0.87 (coverage 1.00, recency 0.94, substance 0.90, impact 0.00)  'RBI rate hike expected in October? What it means for Sensex, Nifty | Experts dec'
- event        score 0.83 (coverage 1.00, recency 0.80, substance 0.90, impact 0.00)  'WACR tops repo rate for first time in nearly 2 months'
- event        score 0.83 (coverage 1.00, recency 0.77, substance 0.90, impact 0.00)  'US Fed, Bank of Japan and others impact on Indian stock markets: Global rate hik'
- event        score 0.82 (coverage 1.00, recency 0.72, substance 0.90, impact 0.00)  'RBI Rate Hike Bets Rise After US Fed Move: Why October Policy Is Now A Close Cal'
- new          score 0.82 (coverage 0.83, recency 1.00, substance 0.50, impact 0.75)  'Yes Bank shares rise 3% after Q2 business update shows loans surging 24% YoY, de'
- new          score 0.80 (coverage 0.67, recency 1.00, substance 0.90, impact 0.85)  'US Stock Market: Wall Street eyes jobs data as rate hike bets and tech volatilit'
- new          score 0.70 (coverage 0.50, recency 1.00, substance 0.90, impact 0.70)  "Kotak Mahindra Bank Primed For Next Leg Of Growth As Street Cheers Anup Saha's E"
- new          score 0.70 (coverage 0.50, recency 1.00, substance 0.90, impact 0.70)  "Anup Bagchi's Appointment Removes Key Overhang For HDFC Bank Stock, Supports Re-"
- new          score 0.66 (coverage 0.50, recency 1.00, substance 0.50, impact 0.85)  'RBI likely intervenes to support rupee, traders say'
- new          score 0.66 (coverage 0.50, recency 1.00, substance 0.50, impact 0.85)  "RBI's dollar inflow measures buy time, but external risks remain"

**CR1**
- announcement score 0.78 (coverage 1.00, recency 0.45, substance 0.90, impact 0.30)  'Kotak Mahindra Bank Limited has informed the Exchange about Investor Presentatio'
- announcement score 0.66 (coverage 1.00, recency 0.53, substance 0.00, impact 0.30)  'Kotak Mahindra Bank Limited has informed the Exchange about General Updates.'

## Previously useful (topical-tagged) items displaced from the selection

- EI3 event: 'Rupee logs weekly decline, with RBI intervention curbing losses' tags=['outlook_demand']
- EI3 event: 'Rupee nudges up on RBI intervention; investors eye inflation data' tags=['rate_policy']
- EI3 new: 'Kotak Mahindra Bank, HDFC Bank, DCX Systems, among buzzing stocks as SENSEX falls over 350' tags=['outlook_demand']
- SR1 event: 'Rupee logs weekly decline, with RBI intervention curbing losses' tags=['outlook_demand']
- SR1 event: 'Rupee nudges up on RBI intervention; investors eye inflation data' tags=['rate_policy']
- SR1 new: 'Kotak Mahindra Bank, HDFC Bank, DCX Systems, among buzzing stocks as SENSEX falls over 350' tags=['outlook_demand']
- MP1 event: 'Rupee logs weekly decline, with RBI intervention curbing losses' tags=['outlook_demand']
- MP1 event: 'Federal Reserve announces the leadership and objectives of its task forces to advance the ' tags=['rate_policy']
- MP1 event: 'Rupee nudges up on RBI intervention; investors eye inflation data' tags=['rate_policy']
- MP1 new: 'Kotak Mahindra Bank, HDFC Bank, DCX Systems, among buzzing stocks as SENSEX falls over 350' tags=['outlook_demand']
- MP2 event: 'How will Nifty, Sensex behave on Monday? US Fed rate hike bets, among 4 factors to drive D' tags=['rate_policy']
- MP3 event: 'Rupee logs weekly decline, with RBI intervention curbing losses' tags=['outlook_demand']
- MP3 event: 'Rupee nudges up on RBI intervention; investors eye inflation data' tags=['rate_policy']
- MP3 event: "India's forex reserves fall $18.3 bn as RBI steps in to defend rupee" tags=['outlook_demand']
