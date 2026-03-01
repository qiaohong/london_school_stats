This is the 2nd part of the project for london_school_stats, following london_school_stats_1.md

before executing anything below, ensure there is a git commit on this machine to rever to, incase subsequent steps fail. 

when i ask you to hand off, store the information in handoff_2.md and leave the previous handoff.md untouched, as it should store context from the previous building process. 

below are new instructions. 

## 1. Build more interactive features on the website. 
add the feature so that user can choose a few schools from the drop down list, and compare them. add a clear button to remove all school selections. 

## 2. Try to get extra data. 
i would like to build a more advanced search function, where user simply need to type in a UK post code (or the first part of post code), and the drop down list shows the nearest 10 schools. i think in the original datset we should have each school's post code. 
search internet to find out how to achieve this, and discuss options with me. 

## 3. Improve visualisation. 
build on top of #2 I would like to display the post code and the schools on a map. 
find out how to achieve this and discuss options with me. 
also think if we should refactor the front end code as the html file is likely getting too big. research best practices and discuss options. 

## 4. Revise to add more flexibilityno 
Build on top of what we have done. But instead of limiting to 10 schools, ask the users to input post code AND a radius in km then display all schools within the radius, sorted from closet to furthest. 
allow user to specify which phases of school do they want to see. make it multiple choice. 
cap the result at radius <= 5km AND 50 schools. 