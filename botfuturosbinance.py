#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Bot de Futuros USD para el par SOL/USDT
- Apalancamiento configurable (en este ejemplo, 10x)
- Utiliza dos EMAs: rápida de 40 y lenta de 99, en un gráfico de velas de 1 minuto
- Opera en LONG y SHORT, utilizando el 95% del capital disponible
- Al abrir una posición, coloca un trailing stop del 1.0% (sin stop loss fijo)
- Gestiona órdenes conflictivas y registra eventos en un archivo CSV
- Incluye lógica de reconexión ante errores
"""

import os
import csv
import time
import datetime
import logging
import math
import pandas as pd
from binance.client import Client
from binance.exceptions import BinanceAPIException

# Configurar logging básico en consola
logging.basicConfig(level=logging.INFO)

class FuturesBot:
    def __init__(self, api_key, api_secret, symbol="ETHUSDT", leverage=10, base_capital_pct=0.95,
                 fast_ema_period=40, slow_ema_period=99, interval="5m"):
        # Guardamos las credenciales para posibles reconexiones
        self.api_key = api_key
        self.api_secret = api_secret
        self.client = Client(api_key, api_secret)
        self.symbol = symbol              # Par de trading
        self.leverage = leverage          # Apalancamiento configurado
        self.base_capital_pct = base_capital_pct  # Porcentaje del capital a usar (95%)
        self.fast_ema_period = fast_ema_period    # Período para EMA rápida
        self.slow_ema_period = slow_ema_period    # Período para EMA lenta
        self.interval = interval          # Intervalo de velas (5 minutos)
        self.log_file = "trading_log.csv" # Archivo para registrar eventos
        self.setup_csv()                  # Configuramos el archivo CSV de logs
        self.set_leverage()               # Establecemos el apalancamiento en Binance

    def setup_csv(self):
        """Crea el archivo CSV si no existe y escribe el header."""
        if not os.path.exists(self.log_file):
            with open(self.log_file, mode='w', newline='') as file:
                writer = csv.writer(file)
                writer.writerow(["timestamp", "event", "details"])

    def log(self, event, details=""):
        """Registra en consola y en el archivo CSV cada evento."""
        timestamp = datetime.datetime.now().isoformat()
        log_entry = [timestamp, event, details]
        with open(self.log_file, mode='a', newline='') as file:
            writer = csv.writer(file)
            writer.writerow(log_entry)
        print(timestamp, event, details)

    def set_leverage(self):
        """Establece el apalancamiento para el símbolo en Binance Futuros."""
        try:
            response = self.client.futures_change_leverage(symbol=self.symbol, leverage=self.leverage)
            self.log("Leverage set", f"Apalancamiento configurado a {self.leverage} para {self.symbol}")
        except BinanceAPIException as e:
            self.log("Error setting leverage", str(e))

    def get_klines(self, limit=500):
        """
        Obtiene datos históricos de velas (klines) para el símbolo e intervalo configurados.
        Se convierten a DataFrame para facilitar el cálculo de indicadores.
        """
        try:
            klines = self.client.futures_klines(symbol=self.symbol, interval=self.interval, limit=limit)
            df = pd.DataFrame(klines, columns=[
                'open_time', 'open', 'high', 'low', 'close', 'volume',
                'close_time', 'quote_asset_volume', 'number_of_trades',
                'taker_buy_base_asset_volume', 'taker_buy_quote_asset_volume', 'ignore'
            ])
            # Conversión de tipos
            df['open'] = pd.to_numeric(df['open'])
            df['high'] = pd.to_numeric(df['high'])
            df['low'] = pd.to_numeric(df['low'])
            df['close'] = pd.to_numeric(df['close'])
            df['open_time'] = pd.to_datetime(df['open_time'], unit='ms')
            return df
        except Exception as e:
            self.log("Error fetching klines", str(e))
            return None

    def calculate_ema(self, df):
        """Calcula las EMAs (rápida y lenta) y las añade al DataFrame."""
        df['ema_fast'] = df['close'].ewm(span=self.fast_ema_period, adjust=False).mean()
        df['ema_slow'] = df['close'].ewm(span=self.slow_ema_period, adjust=False).mean()
        return df

    def determine_signal(self, df):
        """
        Determina la señal de trading basándose en el cruce de las EMAs.
        - Si la EMA rápida cruza de abajo hacia arriba la lenta: señal LONG.
        - Si la EMA rápida cruza de arriba hacia abajo la lenta: señal SHORT.
        """
        if len(df) < 2:
            return None
        last_row = df.iloc[-1]
        prev_row = df.iloc[-2]
        prev_diff = prev_row['ema_fast'] - prev_row['ema_slow']
        current_diff = last_row['ema_fast'] - last_row['ema_slow']
        if prev_diff <= 0 and current_diff > 0:
            return "LONG"
        elif prev_diff >= 0 and current_diff < 0:
            return "SHORT"
        else:
            return None

    def get_available_balance(self):
        """Obtiene el balance disponible en USDT para operar en Futuros."""
        try:
            balance_data = self.client.futures_account_balance()
            for asset in balance_data:
                if asset['asset'] == 'USDT':
                    return float(asset['availableBalance'])
            return 0.0
        except Exception as e:
            self.log("Error fetching balance", str(e))
            return 0.0

    def round_quantity(self, quantity):
        """
        Redondea la cantidad de acuerdo al filtro LOT_SIZE y a quantityPrecision (si está disponible).
        Se utiliza math.floor para redondear hacia abajo y cumplir con el step size.
        Para SOLUSDT se fuerza una precisión de 3 decimales si no se obtiene otra.
        """
        try:
            symbol_info = self.client.get_symbol_info(self.symbol)
            # Obtener precision del símbolo, si está disponible
            quantity_precision = None
            if "quantityPrecision" in symbol_info and symbol_info["quantityPrecision"] is not None:
                quantity_precision = int(symbol_info["quantityPrecision"])
            # Si es SOLUSDT y no se obtuvo precision, forzamos 3 decimales
            if self.symbol == "SOLUSDT" and quantity_precision is None:
                quantity_precision = 2
            step_size = None
            for f in symbol_info['filters']:
                if f['filterType'] == 'LOT_SIZE':
                    step_size = float(f['stepSize'])
                    break
            if step_size is None:
                rounded = round(quantity, quantity_precision if quantity_precision is not None else 3)
                self.log("round_quantity", f"Step size no encontrado; usando {rounded}")
                return rounded

            # Redondea hacia abajo según el step_size
            rounded_quantity = math.floor(quantity / step_size) * step_size
            if quantity_precision is not None:
                final_quantity = round(rounded_quantity, quantity_precision)
            else:
                precision = int(round(-math.log(step_size, 10), 0))
                final_quantity = round(rounded_quantity, precision)
            self.log("round_quantity", f"quantity: {quantity}, step_size: {step_size}, quantity_precision: {quantity_precision}, final_quantity: {final_quantity}")
            return final_quantity
        except Exception as e:
            self.log("Error rounding quantity", str(e))
            return round(quantity, 3)

    def calculate_order_quantity(self, entry_price):
        """
        Calcula la cantidad a operar basándose en el capital disponible,
        el porcentaje de uso y el apalancamiento.
        Fórmula: (balance * porcentaje * leverage) / precio de entrada.
        """
        balance = self.get_available_balance()
        capital_to_use = balance * self.base_capital_pct
        quantity = (capital_to_use * self.leverage) / entry_price
        return self.round_quantity(quantity)

    def place_order(self, signal, entry_price):
        """
        Coloca una orden de mercado para abrir la posición:
        - LONG: compra (SIDE_BUY)
        - SHORT: venta (SIDE_SELL)
        """
        quantity = self.calculate_order_quantity(entry_price)
        side = Client.SIDE_BUY if signal == "LONG" else Client.SIDE_SELL
        try:
            order = self.client.futures_create_order(
                symbol=self.symbol,
                side=side,
                type='MARKET',
                quantity=quantity,
                reduceOnly=False
            )
            self.log("Order placed", f"Señal: {signal}, Cantidad: {quantity}, Precio de entrada: {entry_price}")
            return order
        except BinanceAPIException as e:
            self.log("Error placing order", str(e))
            return None

    def place_trailing_stop(self, signal, quantity):
        """
        Coloca una orden de trailing stop fija del 1%.
        Se utiliza callbackRate=0.65 para establecer la distancia del trailing stop.
        Se fuerza el uso de la cantidad redondeada.
        Se implementa un reintento en caso de error.
        """
        quantity = self.round_quantity(quantity)
        try:
            order = self.client.futures_create_order(
                symbol=self.symbol,
                side=Client.SIDE_SELL if signal == "LONG" else Client.SIDE_BUY,
                type='TRAILING_STOP_MARKET',
                quantity=quantity,
                callbackRate=1.0,  # Trailing stop del 1%
                timeInForce='GTC',
                reduceOnly=True
            )
            self.log("Trailing stop placed", f"Callback Rate: 1.00%, Cantidad: {quantity}")
            return order
        except BinanceAPIException as e:
            self.log("Error placing trailing stop", str(e))
            # Reintento único
            try:
                self.log("Retrying trailing stop", f"Intento de reenvío con cantidad: {quantity}")
                order = self.client.futures_create_order(
                    symbol=self.symbol,
                    side=Client.SIDE_SELL if signal == "LONG" else Client.SIDE_BUY,
                    type='TRAILING_STOP_MARKET',
                    quantity=quantity,
                    callbackRate=0.5,
                    timeInForce='GTC',
                    reduceOnly=True
                )
                self.log("Trailing stop placed on retry", f"Callback Rate: 1.00%, Cantidad: {quantity}")
                return order
            except BinanceAPIException as e2:
                self.log("Error placing trailing stop on retry", str(e2))
                return None

    def check_and_place_trailing_stop(self, signal, quantity):
        """
        Verifica si ya existe una orden TRAILING_STOP_MARKET para el símbolo.
        Si no existe, intenta colocarla.
        """
        try:
            open_orders = self.client.futures_get_open_orders(symbol=self.symbol)
            has_trailing = any(order['type'] == 'TRAILING_STOP_MARKET' for order in open_orders)
            if has_trailing:
                self.log("Trailing stop check", "Ya existe una orden de trailing stop activa.")
            else:
                self.log("Trailing stop check", "No se encontró trailing stop. Colocando uno.")
                self.place_trailing_stop(signal, quantity)
                self.log("Trailing stop action", "Trailing stop colocado exitosamente.")
        except BinanceAPIException as e:
            self.log("Error checking trailing stop", str(e))

    def manage_stop_orders(self, signal):
        """
        Verifica si existen órdenes de stop conflictivas (STOP_MARKET y TRAILING_STOP_MARKET)
        y cancela la que no corresponda para evitar conflictos.
        """
        try:
            open_orders = self.client.futures_get_open_orders(symbol=self.symbol)
            stop_market_order = None
            trailing_stop_order = None
            for order in open_orders:
                if order['type'] == 'STOP_MARKET':
                    stop_market_order = order
                if order['type'] == 'TRAILING_STOP_MARKET':
                    trailing_stop_order = order
            # Si existen ambos, se cancela la orden STOP_MARKET
            if stop_market_order and trailing_stop_order:
                self.client.futures_cancel_order(symbol=self.symbol, orderId=stop_market_order['orderId'])
                self.log("Canceled stop loss order", "Se canceló la orden STOP_MARKET debido a TRAILING_STOP_MARKET activa")
        except BinanceAPIException as e:
            self.log("Error managing stop orders", str(e))

    def reconnect(self):
        """
        Intenta reestablecer la conexión re-inicializando el cliente de Binance.
        Se utiliza en caso de errores críticos o problemas de conectividad.
        """
        self.log("Attempting reconnection", "Reinicializando el cliente de Binance")
        try:
            self.client = Client(self.api_key, self.api_secret)
            self.set_leverage()
            self.log("Reconnection successful", "Cliente reinicializado exitosamente")
        except Exception as e:
            self.log("Reconnection failed", str(e))

    def run(self):
        """
        Bucle principal del bot:
        - Obtiene los datos de velas y calcula indicadores (EMAs).
        - Verifica continuamente si existe una posición abierta.
          * Si existe, verifica si tiene trailing stop y, de no tenerlo, lo coloca.
        - Si no hay posición abierta, verifica si se genera una señal para abrir una posición,
          y en caso afirmativo, abre la posición y coloca el trailing stop.
        - Registra cada acción y, en caso de error, intenta reconectar.
        - El bucle se ejecuta cada 10 segundos, y tras un error se espera 60 segundos.
        """
        while True:
            try:
                df = self.get_klines(limit=100)
                if df is None:
                    time.sleep(60)
                    continue
                df = self.calculate_ema(df)
                signal = self.determine_signal(df)
                
                # Verificamos si ya hay posición abierta
                positions = self.client.futures_position_information(symbol=self.symbol)
                open_positions = [pos for pos in positions if pos['symbol'] == self.symbol and float(pos['positionAmt']) != 0]
                if open_positions:
                    self.log("Position check", "Posición abierta detectada.")
                    # Tomar la cantidad absoluta de la posición abierta
                    pos_qty = abs(float(open_positions[0]['positionAmt']))
                    pos_qty = self.round_quantity(pos_qty)
                    # Si no se genera una nueva señal, inferimos el lado basado en la posición
                    if signal is None:
                        signal = "LONG" if float(open_positions[0]['positionAmt']) > 0 else "SHORT"
                    self.check_and_place_trailing_stop(signal, pos_qty)
                else:
                    # Si no hay posición abierta, verificamos la señal para abrir una posición.
                    if signal:
                        entry_price = float(df.iloc[-1]['close'])
                        order = self.place_order(signal, entry_price)
                        if order is not None:
                            quantity = self.calculate_order_quantity(entry_price)
                            self.place_trailing_stop(signal, quantity)
                            self.manage_stop_orders(signal)
                    else:
                        self.log("No signal", "Sin señal de trading en este momento")
            except Exception as e:
                self.log("Error in main loop", str(e))
                self.reconnect()
                time.sleep(60)
            time.sleep(60)

if __name__ == "__main__":
    # REEMPLAZA 'TU_API_KEY' y 'TU_API_SECRET' con tus credenciales de Binance
    API_KEY = "TU_API"
    API_SECRET = "TU_API_KEY"
    
    bot = FuturesBot(api_key=API_KEY, api_secret=API_SECRET, leverage=10)
    bot.run()
