import pandas as pd
import seaborn as sns
sns.set_style("darkgrid")
import streamlit as st
from get_daily_summaries import download_data, data_exists, insert_into_psql
from psql_config import psql_params
import psycopg2
import SessionState
import plotly.express as px
from statsmodels.tsa.ar_model import AutoReg
from sklearn.metrics import mean_absolute_error


html_header = """
	<head>
	<link rel="stylesheet"href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0-beta3/css/all.min.css"integrity="sha512-Fo3rlrZj/k7ujTnHg4CGR2D7kSs0v4LLanw2qksYuRlEzO+tcaEPQogQ0KaoGN26/zrn20ImR1DfuLWnOo7aBA==" crossorigin="anonymous" referrerpolicy="no-referrer" />
	</head>
	<a href="https://crisleaf.github.io/apps.html">
		<i class="fas fa-arrow-left"></i>
	</a>
	<h2 style="text-align:center;">Simulador de Temperaturas</h2>
	<style>
		i {
			font-size: 30px;
			color: #222;
		}
		i:hover {
			color: cornflowerblue;
			transition: color 0.3s ease;
		}
	</style>
"""
st.markdown(html_header, unsafe_allow_html=True)

city = st.text_input("Ciudad:", placeholder="Ingrese la ciudad... (ex: New York)").lower()
country = st.text_input("País:", placeholder="Ingrese el país... (ex: United States)").lower()

sarimax_iterations = 100

def get_graphics(city, country):
	# PSQL
	conn = psycopg2.connect(**psql_params)
	curr = conn.cursor()
	curr.execute("""SELECT * FROM temperatures""")
	df = pd.DataFrame(curr.fetchall())[[3, 4, 5]]
	df.columns = ["Date", "Max. Temperature", "Min. Temperature"]
	df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
	df.set_index("Date", inplace=True)
	df["Max. Temperature"] = df["Max. Temperature"].apply(lambda x: int(x))
	df["Min. Temperature"] = df["Min. Temperature"].apply(lambda x: int(x))
	conn.commit()
	curr.close()
	conn.close()
	
	# Diaria
	html_title1 = """<h3 style="text-align:center;">Temperatura diaria</h3>"""
	st.markdown(html_title1, unsafe_allow_html=True)
	st.write(f"Primeros datos ingresados en {city.capitalize()}, {country.capitalize()}:")
	st.write(df.head(5))
	st.write(f"Últimos datos ingresados en {city.capitalize()}, {country.capitalize()}:")
	st.write(df.tail(5))
	st.write(f"Número total de filas:", df.shape[0])
	
	# Mensual
	html_title2 = """<h3 style="text-align:center;">Temperatura Promedio Mensual</h3>"""
	st.markdown(html_title2, unsafe_allow_html=True)
	monthly_df = df.groupby(pd.Grouper(freq="M")).mean()
	
	fig1 = px.line(monthly_df["Max. Temperature"],
				   title="Promedio de temperatura máxima mensual:",
				   labels={"value": "Temperatura (°K)", "Date": "Año"})
	st.write(fig1)
	fig2 = px.line(monthly_df["Min. Temperature"],
				   title="Promedio de temperatura mínima mensual:",
				   labels={"value": "Temperatura (°K)", "Date": "Año"})
	st.write(fig2)
	
	# Anual
	html_title3 = """<h3 style="text-align:center;">Temperatura Promedio Anual</h3>"""
	st.markdown(html_title3, unsafe_allow_html=True)
	
	yearly_df = df.groupby(pd.Grouper(freq="Y")).mean()
	fig3 = px.line(yearly_df["Max. Temperature"],
				   title="Promedio de temperatura máxima anual:",
				   labels={"value": "Temperatura (°K)", "Date": "Año"})
	st.write(fig3)
	fig4 = px.line(yearly_df["Min. Temperature"],
				   title="Promedio de temperatura mínima anual:",
				   labels={"value": "Temperatura (°K)", "Date": "Año"})
	st.write(fig4)
	
	# Predicciones
	html_title4 = """<h3 style="text-align:center;">Apendizaje Automático</h3>"""
	st.markdown(html_title4, unsafe_allow_html=True)
	
	monthly_df["tmax_diff"] = monthly_df["Max. Temperature"].diff(1)
	monthly_df["tmax_lag"] = monthly_df["Max. Temperature"].shift(1)
	monthly_df["tmin_diff"] = monthly_df["Min. Temperature"].diff(1)
	monthly_df["tmin_lag"] = monthly_df["Min. Temperature"].shift(1)
	monthly_df.dropna(inplace=True)
	
	## tmax
	st.write("Entrenamos un modelo de Regresión Lineal para la temperatura máxima mensual, "
			 "y obtenemos la siguiente tendencia:")
	reg_fig1 = px.scatter(yearly_df["Max. Temperature"], trendline="ols")
	st.write(reg_fig1)
	
	tmax_model = AutoReg(monthly_df["tmax_diff"], lags=12)
	tmax_model_fit = tmax_model.fit()
	tmax_residuals = tmax_model_fit.resid
	tmax_res_fig = px.scatter(tmax_residuals,
							  labels={"value": "Temperatura (°K)", "Date": "Año"})
	st.write("Ahora, entrenamos un modelo de Series de Tiempo para la temperatura máxima mensual, "
			 "y obtenemos los siguientes residuales:")
	st.write(tmax_res_fig)
	
	tmax_resid = tmax_model_fit.predict().dropna()
	ma_tmax_predictions = monthly_df["tmax_lag"].iloc[12:] + tmax_resid
	tmax_mae = mean_absolute_error(monthly_df["Max. Temperature"].iloc[12:], ma_tmax_predictions)
	st.write(f"Promedio de Error Absoluto Mensual:", round(tmax_mae, 2))
	
	st.write("Predicción Anual en el conjunto de entrenamiento:")
	yearly_df = monthly_df.iloc[12:].groupby(pd.Grouper(freq="Y")).mean()
	ma_tmax_yearly_prediction = ma_tmax_predictions.groupby(pd.Grouper(freq="Y")).mean()
	tmax_pred_df = pd.concat([yearly_df["Max. Temperature"], ma_tmax_yearly_prediction], axis=1)
	tmax_pred_df.columns = ["Original", "Predicción"]
	tmax_pred_fig = px.line(tmax_pred_df,
							labels={"value": "Temperatura (°K)", "index": "Año"})
	st.write(tmax_pred_fig)
	
	## tmin
	st.write("Entrenamos un modelo de Regresión Lineal para la temperatura mínima mensual, "
			 "y obtenemos la siguiente tendencia:")
	reg_fig2 = px.scatter(yearly_df["Min. Temperature"], trendline="ols")
	st.write(reg_fig2)
	
	tmin_model = AutoReg(monthly_df["tmin_diff"], lags=12)
	tmin_model_fit = tmin_model.fit()
	tmin_residuals = tmin_model_fit.resid
	tmin_res_fig = px.scatter(tmin_residuals,
							  labels={"value": "Temperatura (°K)", "Date": "Año"})
	st.write("Ahora, entrenamos un modelo de Series de Tiempo para la temperatura mínima mensual, "
			 "y obtenemos los siguientes residuales:")
	st.write(tmin_res_fig)
	
	tmin_resid = tmin_model_fit.predict().dropna()
	ma_tmin_predictions = monthly_df["tmin_lag"].iloc[12:] + tmin_resid
	tmin_mae = mean_absolute_error(monthly_df["Min. Temperature"].iloc[12:], ma_tmin_predictions)
	st.write(f"Promedio de Error Absoluto Mensual:", round(tmin_mae, 2))
	
	st.write("Predicción Anual en el conjunto de entrenamiento:")
	yearly_df = monthly_df.iloc[12:].groupby(pd.Grouper(freq="Y")).mean()
	ma_tmin_yearly_prediction = ma_tmin_predictions.groupby(pd.Grouper(freq="Y")).mean()
	tmin_pred_df = pd.concat([yearly_df["Min. Temperature"], ma_tmin_yearly_prediction], axis=1)
	tmin_pred_df.columns = ["Original", "Predicción"]
	tmin_pred_fig = px.line(tmin_pred_df,
							labels={"value": "Temperatura (°K)", "index": "Año"})
	st.write(tmin_pred_fig)
	
obtener_btn = st.empty()
ss = SessionState.get(obtener_btn=False)

if obtener_btn.button("Obtener"):
	ss.obtener_btn = True
	
	if data_exists(city, country):
		get_graphics(city, country)
		html_source_code = """
				<p class="source-code">Código Fuente:
				<a href="https://github.com/CrisLeaf/ny_is_burning/blob/master/temperature_analysis.ipynb">
				<i class="fab fa-github"></i></a></p>
				<style>
					.source-code {
						text-align: right;
					}
				</style>
			"""
		st.markdown(html_source_code, unsafe_allow_html=True)
	else:
		st.write("Obteniendo datos...")
		try:
			new_data = download_data(city, country)
			insert_into_psql(city, country, new_data)
			get_graphics(city, country)
		except:
			st.write(f"{city.capitalize()}, {country.capitalize()} no se encuentra disponible.\n"
					 f"Para más información visite")
			st.write(
				"https://www.ncei.noaa.gov/access/search/dataset-search?text=daily%20summaries"
			)