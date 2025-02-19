import streamlit as st
st.set_page_config(
    layout="wide"
)

import os
import pathlib
import app.pages.utils.system_operation_prerun as helper

import pandas as pd
import pypsa
import numpy as np
import plotly.express as px
import xarray as xr
import geopandas as gpd
import plotly.graph_objects as go
import shapely.geometry
import math
import yaml
import hvplot.pandas
import holoviews as hv
from bokeh.models import HoverTool  
from bokeh.plotting import figure, show
from holoviews import Store
import networkx as nx
import hvplot.networkx as hvnx
from shapely.geometry import Point, LineString, shape
import datetime

# needed to change cursor mode of selectboxes from the default text mode
fix_cursor_css = '''
    <style>
        .stSelectbox:first-of-type > div[data-baseweb="select"] > div {
            cursor: pointer;      
        }            
    </style>
'''

non_empth_links_keys=[param for param in helper.config["links_t_parameter"]]
non_empth_loads_keys=[param for param in helper.config["loads_t_parameter"]]
non_empth_stores_keys=[param for param in helper.config["stores_t_parameter"]]

gen_df = helper.get_gen_t_dict()
storage_df = helper.get_storage_t_dict()
links_df = helper.get_links_t_dict("links_t", non_empth_links_keys)
loads_df = helper.get_links_t_dict("loads_t", non_empth_loads_keys)
stores_df = helper.get_links_t_dict("stores_t", non_empth_stores_keys)

res_choices = helper.config["operation"]["resolution"]

kwargs = dict(
        stacked=True,
        line_width=0,
        xlabel="",
        width=800,
        height=550,
        hover=False,
        legend='top'
    )
plot_font_dict = dict(
    title=18,
    legend=18,
    labels=18, 
    xticks=18, 
    yticks=18,
)

st.title("System operation")

_, main_col, _, suppl_col, _ = st.columns([1, 35, 1, 20, 1])

def scenario_formatter(scenario):
    return helper.config["scenario_names"][scenario]

def get_carrier_map():
    return helper.config["carrier"]

def get_colors_map():
    return helper.config["tech_colors"]  

carriers_map = get_carrier_map()
tech_map = dict(map(reversed, carriers_map.items()))
tech_colors = get_colors_map()

with main_col:
    selected_network = st.selectbox(
        "Select which scenario's plot you want to see :",
        list(gen_df.keys()),
        format_func = scenario_formatter,
        help="You can choose between available scenarios"
    )
    st.markdown(fix_cursor_css, unsafe_allow_html=True)

# the finest available resolution depends on the model
finest_resolution = helper.get_meta_df(selected_network)["scenario"]["opts"][0].split("L-")[1]
finest_resolution_name = finest_resolution.split("H")[0] + "-hourly"
upd_dict = {finest_resolution: finest_resolution_name}
upd_dict.update(res_choices)

with suppl_col:
    choices = upd_dict
    res = st.selectbox(
        "Resolution",
        choices,
        format_func=lambda x: choices[x], 
        key="gen_res",
        help="You can choose a resolution for time aggregation applied for a plot"
    )
    st.markdown(fix_cursor_css, unsafe_allow_html=True) 


country_data=gen_df.get(selected_network)


##################### generators #####################
# _, gen_param_col, _, res_param_col,_ ,date_range_param, _ = st.columns([1,20,1,20,1,50,1])
_, date_range_param, _ = st.columns([1, 50, 1])
_, gen_plot_col, _ = st.columns([1, 80, 1])

gen_df=country_data["p"].drop("Load", axis=1, errors="ignore")

with date_range_param:
    min_index=gen_df.index[0]
    max_index=gen_df.index[-1]
    min_value = datetime.datetime(min_index.year, min_index.month, min_index.day)
    max_value = datetime.datetime(max_index.year, max_index.month, max_index.day)
    values = st.slider(
            'Select a range of values',
            min_value, max_value, (min_value, max_value),
            # step=datetime.timedelta(hours=int(res[:-1])),
            format="D MMM, HH:mm",
            label_visibility='hidden',
            key="gen_date"
        )

gen_df = gen_df.loc[values[0]:values[1]].resample(res).mean()

df_techs = [tech_map[c] for c in gen_df.columns]
plot_color = [tech_colors[c] for c in df_techs]
ylab = helper.config["gen_t_parameter"]["p"]["nice_name"] + " ["+str(helper.config["gen_t_parameter"]["p"]["unit"] + "]")

gen_area_plot = gen_df.hvplot.area(
    **kwargs,
    ylabel=ylab, 
    group_label=helper.config["gen_t_parameter"]["p"]["legend_title"],
    color=plot_color) 
gen_area_plot = gen_area_plot.opts(
    fontsize=plot_font_dict
)
s=hv.render(gen_area_plot, backend='bokeh')

with gen_plot_col:
    st.bokeh_chart(s, use_container_width=True)


##################### demand #####################
links_country_data=links_df.get(selected_network)
loads_country_data=loads_df.get(selected_network)
stores_country_data=stores_df.get(selected_network)

links_df = links_country_data["p0"]
loads_df = loads_country_data["p"]
stores_df = stores_country_data["p"]

# TODO Remove hard-coding
h2_cols = [col for col in stores_df.columns if "H2" in col]
battery_cols = [col for col in stores_df.columns if "battery" in col]

demand_df=pd.DataFrame({"load": loads_df.sum(axis=1)})
demand_df["H2"]=stores_df[h2_cols].sum(axis=1)
demand_df["battery"]=stores_df[battery_cols].sum(axis=1)

demand_df=demand_df.loc[values[0]:values[1]].resample(res).mean()

plot_color = [tech_colors[c] for c in demand_df.columns]
ylab = helper.config["loads_t_parameter"]["p"]["nice_name"] + " ["+str(helper.config["loads_t_parameter"]["p"]["unit"] + "]")

_, links_plot_col, _ = st.columns([1, 80, 1])
with links_plot_col:
    demand_area_plot=demand_df.hvplot.area(
        **kwargs,
        ylabel=ylab,
        group_label=helper.config["loads_t_parameter"]["p"]["legend_title"],
        color = plot_color
        )
    demand_area_plot = demand_area_plot.opts(
        fontsize=plot_font_dict
    )         
    s2=hv.render(demand_area_plot, backend='bokeh')
    st.bokeh_chart(s2, use_container_width=True)


# ##################### storage #####################

# st.subheader("Storage plot is here.")

# _, storage_param_col,_,res_param_col,_,date_range_param, _ = st.columns([1,20,1,20,1,50,1])
# _, storage_plot_col, _ = st.columns([1,80,1])

# storage_country_data=storage_df.get(selected_network)

# def storage_formatter(storage):
#     return helper.config["storage_t_parameter"][storage]["nice_name"] + " "+helper.config["storage_t_parameter"][storage]["unit"]

# with storage_param_col:
#     selected_storage = st.selectbox(
#         "options",
#         list(storage_country_data.keys()),
#         format_func=storage_formatter
#     )

# storage_df=storage_country_data[selected_storage]

# with res_param_col:
#     choices = res_choices
#     res = st.selectbox("Resolution", choices, format_func=lambda x: choices[x],key="storage_res")

# with date_range_param:
#     min_index=storage_df.index[0]
#     max_index=storage_df.index[-1]
#     min_value = datetime.datetime(min_index.year, min_index.month, min_index.day,max_index.hour,max_index.minute)
#     max_value = datetime.datetime(max_index.year, max_index.month, max_index.day,max_index.hour,max_index.minute)
#     values = st.slider(
#             'Select a range of values',
#             min_value, max_value, (min_value, max_value),
#             # step=datetime.timedelta(hours=int(res[:-1])),
#             format="D MMM, HH:mm",
#             label_visibility='hidden',
#             key="storage_date"
#         )

# storage_df=storage_df.loc[values[0]:values[1]].resample(res).mean()

# with storage_plot_col:
#     storage_area_plot=storage_df.hvplot.area(**kwargs,
#     ylabel=helper.config["storage_t_parameter"][selected_storage]["unit"],
#     group_label=helper.config["storage_t_parameter"][selected_storage]["legend_title"])
#     s=hv.render(storage_area_plot,backend='bokeh')
#     st.bokeh_chart(s, use_container_width=True)
