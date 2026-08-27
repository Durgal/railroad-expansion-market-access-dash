from pathlib import Path
import geopandas as gpd
import pandas as pd
import plotly.graph_objects as go
from dash import Dash, dcc, html, Input, Output

COLORS = {
    "background": "#2B2118",
    "railroad": "#E8D8B0",
    "river": "#536F73",
    "county": "#44372B",
    "state": "#997950",
    "text": "#E5D5B5",
}

ECONOMIC_COLOR_MAP = "magma"

FONT = "Georgia, serif"

BASE_DIRECTORY = Path.cwd()

YEARS = [1840,1850,1860,1870,1880,1890,1900,1910,1920]

COST_FILE = (
    f"{BASE_DIRECTORY}/data/economic/NSFtranspCost.dta"
)

COUNTY_ID_FILE = (
    f"{BASE_DIRECTORY}/data/economic/Cost_ID_county.xlsx"
)

COUNTY_SHAPEFILE = (
    f"{BASE_DIRECTORY}/data/county/US_county_1890.shp"
)

# global variables
RAILROAD_SEGMENTS = []
RIVER_X, RIVER_Y = [],[]
STATE_X, STATE_Y = [],[]
COUNTIES, TRANSPORTATION_COSTS = None, None
MIN_X, MIN_Y = None, None
MAX_X, MAX_Y = None, None

# ------------------------------------------------
# Load Transportation Costs by County
# ------------------------------------------------
def load_economic_data():
    """
    Load all economic data from the COST_FILE to determine the average market
    accessibility of each county measured in cents per ton-mile

    Args:
        N/A
    Return:
        N/A
    """
    cost_columns = (
        ["gisid_origin","gisid_destination"] + [f"cost{year}" for year in YEARS]
    )

    costs = pd.read_stata(
        COST_FILE,
        columns=cost_columns
    )

    county_costs = []

    for year in YEARS:

        column = f"cost{year}"

        # get average transportation costs for each county by year
        yearly_cost = (
            costs.groupby("gisid_origin")[column].mean().reset_index()
        )

        yearly_cost["year"] = int(year)

        yearly_cost = yearly_cost.rename(
            columns={
                "gisid_origin":"gis_id",
                column:"avg_cost"
            }
        )

        county_costs.append(yearly_cost)

    global TRANSPORTATION_COSTS
    TRANSPORTATION_COSTS = pd.concat(county_costs,ignore_index=True)


# ------------------------------------------------
# Load County Geometry
# ------------------------------------------------
def load_county_geometry():
    """
    Load the county shape file to get the GeoDataFrame for COUNTIES

    Args:
        N/A
    Return:
        N/A
    """
    county_ids = pd.read_excel(COUNTY_ID_FILE)

    # select the county ID (NHGISNAM) / State Name (STATENAM)
    county_ids = county_ids[
        [
            "gis id",
            "NHGISNAM",
            "STATENAM"
        ]
    ]

    # rename to match column used in transportation cost data
    county_ids = county_ids.rename(
        columns={"gis id":"gis_id"}
    )

    global COUNTIES
    COUNTIES = gpd.read_file(COUNTY_SHAPEFILE)

    # merge county identification data with the county geometries
    COUNTIES = COUNTIES.merge(
        county_ids.copy(),
        on=["NHGISNAM","STATENAM"],
        how="left"
    )


# ------------------------------------------------
# Create the GeoDataFrame Railroad Segment List (for all years)
# ------------------------------------------------
def load_railroad_geometry():
    """
    Load the railroad shape file to get the GeoDataFrame for RAILROAD_SEGMENTS

    Args:
        N/A
    Return:
        N/A
    """
    for year in YEARS:
        file = Path(f"{BASE_DIRECTORY}/data/geographical/{str(year)}/Component_6_{year}.shp")

        if file.exists():
            railroads = gpd.read_file(file)                         # read the railroad network data file
            railroads.columns = railroads.columns.str.lower()       # normalize the column names to lower case
            railroads["year"] = year                                # create a year column for every year
            railroads["geometry"] = railroads.geometry.simplify(    # create a geometry column with simplified railroad geometry
                tolerance=1000,
                preserve_topology = True
            )
            global RAILROAD_SEGMENTS
            RAILROAD_SEGMENTS.append(railroads)
        else:
            print(f"FILE NOT FOUND: {file}")


# ------------------------------------------------
# Create State Boundary Geometry
# ------------------------------------------------
def load_state_geometry():
    """
    Load the county shape file to get the GeoDataFrame for STATE_X and STATE_Y

    Args:
        N/A
    Return:
        N/A
    """
    # dissolve any geometry where counties of the same state overlap
    states = COUNTIES.dissolve(
        by="STATENAM",
        as_index=False
    )

    # simplify the geometry for optimization
    states["geometry"] = states.geometry.simplify(
        tolerance=1000,
        preserve_topology=True
    )

    state_boundaries = states[["STATENAM", "geometry"]].copy()          # make a copy of all state geometries by state name
    state_boundaries["geometry"] = state_boundaries.geometry.boundary   # get the GeoDataFrame for all state boundaries
    global STATE_X, STATE_Y                                             # access global variables state x / y
    STATE_X, STATE_Y = gdf_to_coordinates(state_boundaries)             # get the list of X / Y coordinates of all state boundaries


# ------------------------------------------------
# Create the GeoDataFrame River Segment List
# ------------------------------------------------
def load_river_geometry():
    """
    Load the county shape file to get the GeoDataFrame for RIVER_X and RIVER_Y

    Args:
        N/A
    Return:
        N/A
    """
    file = Path(f"{BASE_DIRECTORY}/data/geographical/All/Component_0_allyears.shp")

    if file.exists():
        rivers = gpd.read_file(file)
        rivers["geometry"] = rivers.geometry.simplify(
            tolerance=1000,
            preserve_topology = True
        )
    else:
        print(f"FILE NOT FOUND: {file}")

    global RIVER_X, RIVER_Y
    RIVER_X, RIVER_Y = gdf_to_coordinates(rivers)


# ------------------------------------------------
# Obtain Map Boundaries (based on railroad segments)
# ------------------------------------------------
def load_map_boundaries():
    """
    Load the the boundaries for the map based on the railroad geometry

    Args:
        N/A
    Return:
        N/A
    """
    global MIN_X, MIN_Y, MAX_X, MAX_Y
    MIN_X = min(gdf.total_bounds[0] for gdf in RAILROAD_SEGMENTS)
    MIN_Y = min(gdf.total_bounds[1] for gdf in RAILROAD_SEGMENTS)
    MAX_X = max(gdf.total_bounds[2] for gdf in RAILROAD_SEGMENTS)
    MAX_Y = max(gdf.total_bounds[3] for gdf in RAILROAD_SEGMENTS)


# ------------------------------------------------
# Convert GeoDataFrame to Coordinates
# ------------------------------------------------
def gdf_to_coordinates(gdf:gpd.GeoDataFrame):
    """
    Given a GeoDataFrame of either LineString or MultiLineString type return a
    list of x, y values representing the coordinates of the geometry for the GDF

    Args:
        gdf (GeoDataFrame) : the geometry data we want to get the coordinates for
    Return:
        list(float) : the list of x coordinates of the given GDF
        list(float) : the list of y coordinates of the given GDF
    """
    x = []
    y = []

    for geometry in gdf.geometry:
        if geometry.geom_type == "LineString":
            coords = list(geometry.coords)

            x.extend(point[0] for point in coords)
            y.extend(point[1] for point in coords)

            x.append(None)
            y.append(None)

        elif geometry.geom_type == "MultiLineString":
            for line in geometry.geoms:
                coords = list(line.coords)

                x.extend(point[0] for point in coords)
                y.extend(point[1] for point in coords)
                
                x.append(None)
                y.append(None)

    return x,y


# ------------------------------------------------
# Economic County Data Function
# ------------------------------------------------
def add_economic_data_to_figure(fig:go.Figure,counties:gpd.GeoDataFrame,county_cost:pd.DataFrame,year:int):
    """
    Add county-level economic data to the Figure in the form of a scatter plot.
    Every point is drawn to a map and represents a county in the US and the color
    represents the market accessibility of a given county measured in average
    cost per ton-mile to transport goods

    Args:
        fig (Figure): the Plotly figure we are adding the economic data to
        counties (GeoDataFrame): the counties associated with the economic data
        county_cost (DataFrame): the cost per ton-mile by county and year
        year (int): the year of the economic data set
    Return:
        N/A
    """
    yearly_cost = county_cost[county_cost["year"] == year]      # filter yearly cost data to current year
    data = counties.merge(yearly_cost,on="gis_id",how="left")   # match each counties transportation costs to corresponding geometry
    points = data.geometry.representative_point()               # create a point inside each county to represent location on map

    fig.add_trace(
        go.Scattergl(
            x=points.x,
            y=points.y,
            mode="markers",
            name="County",
            marker=dict(
                size=9,
                color=data["avg_cost"],
                colorscale=ECONOMIC_COLOR_MAP,
                showscale=True,
                opacity=0.65,
                colorbar=dict(
                    title=dict(
                        text="¢ / ton-mile",
                        font=dict(
                            family=FONT,
                            color=COLORS["text"]
                        )
                    ),
                    tickfont=dict(
                        family=FONT,
                        color=COLORS["text"]
                    )
                )
            ),

            # county name (NHGISNAM) + state name (STATENAM)
            text=(
                data["NHGISNAM"] + ", " + data["STATENAM"]
            ),

            hovertemplate=(
                "<b>%{text}</b><br>" +                  # county name
                "Average Cost: %{marker.color:.4f}" +   # cent / ton-mile
                "<extra></extra>"                       # remove 'County' classification tag
            )
        )
    )


# ------------------------------------------------
# Add a Line to a Plotly Figure
# ------------------------------------------------
def add_line_to_figure(fig:go.Figure, gdf:gpd.GeoDataFrame, color="black", width=1, name=None):
    """
    Add GeoDataFrame as a line to a pre-existing Figure

    Args:
        fig (Figure): the Plotly figure we are adding the GeoDataFrame to
        gdf (GeoDataFrame): the GeoDataFrame we want to add to the map
        color (str): the color to use for the lines
        width (int): the width of the line
        name  (str): the name of the trace (used in legend)
    Return:
        (Figure) : return the Figure after adding the line
    """

    x,y = gdf_to_coordinates(gdf)

    fig.add_trace(
        go.Scattergl(
            x=x,
            y=y,
            mode="lines",
            line=dict(
                color=color,
                width=width
                ),
            name=name,
            hoverinfo="skip"
        )
    )

    return fig


# ------------------------------------------------
# Convert GeoDataFrame to Plotly Figure
# ------------------------------------------------
def gdf_to_figure(railroads:gpd.GeoDataFrame, counties=None, transportation_cost=None):
    """
    Add the following features into a Plotly Figure
    1. Railroad Geometries
    2. Economic Data per County
    3. State Boundaries
    4. River Geometries

    Args:
        railroads (GeoDataFrame): the railroad segments we want to add to the map
        counties  (GeoDataFrame): the county data we want to add to the map
        transportation_cost (DataFrame): county level transportation cost data
    Return:
        (Figure) : return the Figure after adding all map geometries
    """

    fig = go.Figure()
    year = railroads["year"].iloc[0]

    # Economic Geo Data Layer
    if counties is not None and transportation_cost is not None:
        add_economic_data_to_figure(
            fig,
            counties,
            transportation_cost,
            year
        )

    # State Boundary Geo Data Layer (static)
    fig.add_trace(
        go.Scattergl(
            x=STATE_X,
            y=STATE_Y,
            mode="lines",
            line=dict(
                color=COLORS["state"],
                width=.5
            ),
            name="States",
            hoverinfo="skip"
        )
    )

    # River Geo Data Layer (static)
    fig.add_trace(
        go.Scattergl(
            x=RIVER_X,
            y=RIVER_Y,
            mode="lines",
            line=dict(
                color=COLORS["river"],
                width=1
            ),
            name="Rivers",
            hoverinfo="skip"
        )
    )

    # Railroad Geo Data Layer
    add_line_to_figure(
        fig,
        railroads,
        color=COLORS["railroad"],
        width=1,
        name="Railroads"
    )

    # Map Figure Layout
    fig.update_layout(
        title=f"U.S. Railroad Network - {year}",

        paper_bgcolor=COLORS["background"],
        plot_bgcolor=COLORS["background"],

        font=dict(
            family=FONT,
            color=COLORS["text"]
        ),

        xaxis=dict(
            visible=False,
            range=[MIN_X,MAX_X]
        ),

        yaxis=dict(
            visible=False,
            range=[MIN_Y,MAX_Y],
            scaleanchor="x",
            scaleratio=1
        ),

        showlegend=True,
        legend=dict(
            x=0.01,
            y=0.99,
            bgcolor=COLORS["background"],
            bordercolor=COLORS["text"],
            borderwidth=1,
            font=dict(
                family=FONT,
                color=COLORS["text"]
            )
        ),

        margin=dict(l=0, r=0, t=50, b=0),

        # interface border
        shapes=[
            dict(
                type="rect",
                xref="paper",
                yref="paper",
                x0=0,
                y0=0,
                x1=1,
                y1=1,
                line=dict(color=COLORS["text"],width=2)
            )
        ]
    )

    return fig


# ------------------------------------------------
# Draw Plot for Railroad Length over Time
# ------------------------------------------------
def plot_railroad_length(railroad_segments:list):
    """
    Create scatter plot figure representing U.S. railroad length over time

    Args:
        railroad_segments (list): list of GeoDataFrames containing railroad segments
    Return:
        (Figure) : return the Figure
    """
    fig = go.Figure()

    lengths = []

    # calculate total railroad length in miles for each year
    for railroads in railroad_segments:
        miles = railroads["length"].sum() / 1609.344
        lengths.append(miles)

    fig.add_trace(
        go.Scatter(
            x=YEARS,
            y=lengths,
            mode="lines+markers",
            line=dict(
                color=COLORS["text"],
                width=3
            ),
            marker=dict(size=8),
            hovertemplate=(
                "<b>%{x}</b><br>"                   # year
                "Total Railroad: %{y:,.0f} miles"   # rail road length
                "<extra></extra>"                   # remove trace tag
            )
        )
    )

    fig.update_layout(
        title="Total Railroad Length Over Time",

        paper_bgcolor=COLORS["background"],
        plot_bgcolor=COLORS["background"],

        font=dict(
            family=FONT,
            color=COLORS["text"]
        ),

        xaxis=dict(showgrid=False),
        yaxis=dict(
            title="miles of railroad",
            showgrid=False
        ),
    )

    return fig


# ------------------------------------------------
# Draw Box Plot for Cost per Ton-Mile of Counties over Time
# ------------------------------------------------
def plot_county_cost_distribution(transportation_costs:pd.DataFrame):
    """
    Create box plot figure representing distribution of transportation costs
    across the U.S. counties over a period of time

    Args:
        transportation_costs (DataFrame): DataFrame containing county transportation costs
    Return:
        (Figure) : return the Figure
    """
    fig = go.Figure()

    fig.add_trace(
        go.Box(
            x=transportation_costs["year"],
            y=transportation_costs["avg_cost"],
            boxpoints="outliers",
            line=dict(
                color=COLORS["text"],
                width=3
            ),
            marker=dict(size=5)
        )
    )

    fig.update_layout(
        title="Distribution of Transportation Costs Across U.S. Counties",

        paper_bgcolor=COLORS["background"],
        plot_bgcolor=COLORS["background"],

        font=dict(
            family=FONT,
            color=COLORS["text"]
        ),

        xaxis=dict(showgrid=False),
        yaxis=dict(
            title="¢ / ton-mile",
            showgrid=False
        )
    )

    return fig


# ------------------------------------------------
# Dash Application
# ------------------------------------------------
application = Dash()
server = application.server

def dash_application():
    """
    Dash application that draws:
    1. a map containing railroad / river / economic data from 1840 to 1920
    2. a plot containing total railroad in miles over time
    3. a plot containing median cost / ton-mile to transport goods through U.S. Counties over time

    Args:
        N/A
    Return:
        N/A
    """


    application.layout = html.Div([
        html.H1(
            "U.S. Railroad Expansion & Market Access",
            style={
                "textAlign": "center",
                "fontFamily": FONT,
                "color": COLORS["text"]
                }
        ),

        # Railroad Map
        dcc.Loading(
            dcc.Graph(
                id="railroad-map",
                figure=gdf_to_figure(
                    RAILROAD_SEGMENTS[0],
                    COUNTIES,
                    TRANSPORTATION_COSTS
                    ),
                style={"height": "80vh"}
            ),
            type="circle"
        ),

        # Year Slider
        html.Div([
            html.Label("Year"),
            dcc.Slider(
                id="year-slider",
                min=0,
                max=len(RAILROAD_SEGMENTS)-1,
                step=1,
                value=0,
                marks={
                    i: {
                        "label": str(gdf["year"].iloc[0]),
                        "style": {
                            "color": COLORS["text"],
                            "fontFamily": FONT
                        }
                    } for i, gdf in enumerate(RAILROAD_SEGMENTS)
                }
            )
        ]),

        html.Div([
            # Railroad Length over Time Plot
            dcc.Graph(
                id="railroad-length-over-time",
                figure=plot_railroad_length(RAILROAD_SEGMENTS),
                style={"height": "50vh"}
            ),

            # Median Cost / Ton-Mile per County over Time Plot
            dcc.Graph(
                id="median-county-market-access-over-time",
                figure=plot_county_cost_distribution(TRANSPORTATION_COSTS),
                style={"height": "60vh"}
            )
        ])
    ],

    style={
        "backgroundColor": COLORS["background"],
        "color": COLORS["text"],
        "fontFamily": FONT,
        "padding": "10px 20px"
        
    })

    @application.callback(
        Output("railroad-map","figure"),
        Input("year-slider","value")
    )
    def update_map(year):
        return gdf_to_figure(
            RAILROAD_SEGMENTS[year],
            COUNTIES,
            TRANSPORTATION_COSTS
        )


# ------------------------------------------------
# Main Program
# ------------------------------------------------
def main():
    load_economic_data()
    load_county_geometry()
    load_river_geometry()
    load_railroad_geometry()
    load_state_geometry()
    load_map_boundaries()
    dash_application()


main()