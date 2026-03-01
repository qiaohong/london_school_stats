This document outlines the high level user flow of the final app. We have been building towards it in small steps. Read this plan carefully and think about edge cases and general feasibilities. Create additional project plan md docs beyond the current 3 to break down this project into detailed steps. think about the sequence of building different components. 

1. At the start of the user flow, the user should provide a post code (e.g. office location) and desired commute time in minutes, as well as how strongly the users would like to limit to communite to this limit (if not so strongly, we add +20%). Separately, user should specific the birth year month of their child(ren)

2. The system should work out what stages of school is relevant given the information of the children, and assume that we are interested in the current year group + next 3 years, and produce a short (~3) list of london LAs that fit the commute time criteria. We need to think about how to compute the commute time but let's park it for later. Provide brief rationale of each of the recommended LA. Ask user to confirm choices of LA. 

3. ask for additional criteria of schools with explanations. make some defautl recommendations. 

4. produce a short list of schools and share additional information about the neighbourhood e.g. housing price, housing stock, crime, pollution etc. Ask user to refine the list. 

5. for any single selection of school from this list, look into details in admission criteria and send a search to rightmove with correct distance filter. 


