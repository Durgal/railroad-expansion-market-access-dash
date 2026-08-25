#Railroad Expansion and Market Access

The purpose of this project is to examine the effect that the expansion of railroads had on the American economy.

###Data set used:
"Transportation Economics of the 21st Century" from the National Bureau of Economic Research (NBER)
https://www.nber.org/research/data/transportation-economics-21st-century-rail-data

###This data set contains the following:
1. data/geographical/* : contains shapefiles for the geometries of railroad segments and river segments from 1840 to 1920
2. NFStranspCost.dta   : contains transportation cost data between counties for each decade from 1840 to 1920
3. Cost_ID_county.xlsx : GIS identifiers and county / state names needed to link transportation costs to geographic data
4. US_county_1890.shp  : shapefile containing geometries for all counties in 1890

###Project Structure:
**data/
├─ county/ . . . . . . county centroids and shape file geometries
├─ economic/ . . . . . economic data related to transportation cost in U.S. counties over time
├─ geographical/ . . . shape files for geographic content (railroads, rivers, ports, etc)**


In the early years of this data set you will note that rivers had a marked impact on market access. Goods could be moved along navigable rivers at a cheaper cost than in other areas, with the most stark contrast being the Rocky Mountain area which would have been incredibly difficult to traverse as a trade route. After the transcontinental railroad was completed in 1869 you can see a notable drop in median cost to transport goods through counties, and outliers begin to shrink. The median cost per ton-mile to transport goods through counties drop from 30¢ to 9¢ from 1840 to 1920 as the total length in miles of railroad stretches from ~5000 to 240,000 miles during that time period.

<img src="app-image.png" alt="U.S. Railroad Expansion 1870" width="500">
