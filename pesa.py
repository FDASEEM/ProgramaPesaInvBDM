import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import serial
import serial.tools.list_ports
import threading
import time
import json
from datetime import datetime
import queue

class PesaUSBMonitor:
    def __init__(self, root):
        self.root = root
        self.root.title("Monitor de Pesa USB")
        self.root.geometry("800x600")
        
        # Variables
        self.serial_connection = None
        self.is_connected = False
        self.is_monitoring = False
        self.data_queue = queue.Queue()
        self.peso_actual = 0.0
        self.historial_pesos = []
        self.historial_tiempos = []
        
        # Configurar interfaz
        self.setup_ui()
        
        # Hilo para procesar datos
        self.monitor_thread = None
        self.root.after(100, self.process_queue)
    
    def setup_ui(self):
        # Frame principal
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Configuración de conexión
        conn_frame = ttk.LabelFrame(main_frame, text="Conexión USB", padding="10")
        conn_frame.grid(row=0, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))
        
        ttk.Label(conn_frame, text="Puerto:").grid(row=0, column=0, padx=(0, 5))
        self.puerto_combo = ttk.Combobox(conn_frame, state="readonly", width=20)
        self.puerto_combo.grid(row=0, column=1, padx=(0, 10))
        
        ttk.Button(conn_frame, text="Actualizar Puertos", 
                  command=self.actualizar_puertos).grid(row=0, column=2, padx=(0, 10))
        
        self.btn_conectar = ttk.Button(conn_frame, text="Conectar", 
                                      command=self.toggle_connection)
        self.btn_conectar.grid(row=0, column=3)
        
        # Estado de conexión
        self.status_label = ttk.Label(conn_frame, text="Desconectado", foreground="red")
        self.status_label.grid(row=1, column=0, columnspan=4, pady=(5, 0))
        
        # Display de peso
        peso_frame = ttk.LabelFrame(main_frame, text="Peso Actual", padding="20")
        peso_frame.grid(row=1, column=0, sticky=(tk.W, tk.E), padx=(0, 5))
        
        self.peso_var = tk.StringVar(value="0.00")
        peso_display = ttk.Label(peso_frame, textvariable=self.peso_var, 
                                font=("Arial", 24, "bold"))
        peso_display.grid(row=0, column=0)
        
        ttk.Label(peso_frame, text="kg", font=("Arial", 16)).grid(row=0, column=1, padx=(5, 0))
        
        # Controles
        control_frame = ttk.LabelFrame(main_frame, text="Controles", padding="10")
        control_frame.grid(row=1, column=1, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        self.btn_tara = ttk.Button(control_frame, text="Tara", 
                                  command=self.hacer_tara, state="disabled")
        self.btn_tara.grid(row=0, column=0, pady=(0, 5), sticky=(tk.W, tk.E))
        
        self.btn_guardar = ttk.Button(control_frame, text="Guardar Peso", 
                                     command=self.guardar_peso, state="disabled")
        self.btn_guardar.grid(row=1, column=0, pady=(0, 5), sticky=(tk.W, tk.E))
        
        self.btn_exportar = ttk.Button(control_frame, text="Exportar Datos", 
                                      command=self.exportar_datos)
        self.btn_exportar.grid(row=2, column=0, sticky=(tk.W, tk.E))
        
        # Frame para historial simple
        historial_frame = ttk.LabelFrame(main_frame, text="Últimas Lecturas", padding="10")
        historial_frame.grid(row=2, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(10, 0))
        
        # Listbox para mostrar las últimas lecturas
        self.historial_listbox = tk.Listbox(historial_frame, height=6, font=("Courier", 10))
        scrollbar_hist = ttk.Scrollbar(historial_frame, orient="vertical", command=self.historial_listbox.yview)
        self.historial_listbox.configure(yscrollcommand=scrollbar_hist.set)
        
        self.historial_listbox.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        scrollbar_hist.grid(row=0, column=1, sticky=(tk.N, tk.S))
        
        historial_frame.columnconfigure(0, weight=1)
        historial_frame.rowconfigure(0, weight=1)
        
        # Lista de mediciones guardadas
        list_frame = ttk.LabelFrame(main_frame, text="Mediciones Guardadas", padding="10")
        list_frame.grid(row=3, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(10, 0))
        
        # Treeview para mostrar mediciones
        columns = ("Timestamp", "Peso")
        self.tree = ttk.Treeview(list_frame, columns=columns, show="headings", height=8)
        self.tree.heading("Timestamp", text="Fecha/Hora")
        self.tree.heading("Peso", text="Peso (kg)")
        self.tree.column("Timestamp", width=200)
        self.tree.column("Peso", width=100)
        
        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        
        self.tree.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        
        # Configurar expansión de widgets
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        main_frame.rowconfigure(2, weight=1)
        main_frame.rowconfigure(3, weight=1)
        list_frame.columnconfigure(0, weight=1)
        list_frame.rowconfigure(0, weight=1)
        
        # Inicializar puertos
        self.actualizar_puertos()
    
    def actualizar_puertos(self):
        """Actualiza la lista de puertos COM disponibles"""
        puertos = [port.device for port in serial.tools.list_ports.comports()]
        self.puerto_combo['values'] = puertos
        if puertos:
            self.puerto_combo.set(puertos[0])
    
    def toggle_connection(self):
        """Conectar o desconectar de la pesa"""
        if not self.is_connected:
            self.conectar()
        else:
            self.desconectar()
    
    def conectar(self):
        """Conecta con la pesa USB"""
        puerto = self.puerto_combo.get()
        if not puerto:
            messagebox.showerror("Error", "Selecciona un puerto COM")
            return
        
        try:
            # Ajusta estos parámetros según tu pesa
            self.serial_connection = serial.Serial(
                port=puerto,
                baudrate=9600,  # Común para balanzas
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=1
            )
            
            self.is_connected = True
            self.is_monitoring = True
            
            # Actualizar UI
            self.btn_conectar.config(text="Desconectar")
            self.status_label.config(text="Conectado", foreground="green")
            self.btn_tara.config(state="normal")
            self.btn_guardar.config(state="normal")
            self.puerto_combo.config(state="disabled")
            
            # Iniciar monitoreo
            self.monitor_thread = threading.Thread(target=self.monitor_peso, daemon=True)
            self.monitor_thread.start()
            
            messagebox.showinfo("Éxito", f"Conectado al puerto {puerto}")
            
        except serial.SerialException as e:
            messagebox.showerror("Error de Conexión", f"No se pudo conectar: {e}")
    
    def desconectar(self):
        """Desconecta de la pesa"""
        self.is_monitoring = False
        self.is_connected = False
        
        if self.serial_connection:
            self.serial_connection.close()
            self.serial_connection = None
        
        # Actualizar UI
        self.btn_conectar.config(text="Conectar")
        self.status_label.config(text="Desconectado", foreground="red")
        self.btn_tara.config(state="disabled")
        self.btn_guardar.config(state="disabled")
        self.puerto_combo.config(state="readonly")
    
    def monitor_peso(self):
        """Hilo que lee continuamente el peso de la pesa"""
        while self.is_monitoring:
            try:
                if self.serial_connection and self.serial_connection.in_waiting > 0:
                    # Lee datos del puerto serie
                    data = self.serial_connection.readline().decode('utf-8').strip()
                    
                    # Procesa los datos (esto dependerá del formato de tu pesa)
                    peso = self.parsear_peso(data)
                    if peso is not None:
                        self.data_queue.put(("peso", peso))
                
                time.sleep(0.1)  # 10 Hz de actualización
                
            except Exception as e:
                self.data_queue.put(("error", str(e)))
                break
    
    def parsear_peso(self, data):
        """
        Parsea los datos recibidos de la pesa.
        IMPORTANTE: Ajusta esta función según el protocolo de tu pesa específica.
        """
        try:
            # Ejemplo genérico - muchas balanzas envían formato "WT: 1.234 kg"
            if "WT:" in data:
                peso_str = data.split("WT:")[1].split("kg")[0].strip()
                return float(peso_str)
            
            # Otro formato común - solo números
            elif data.replace(".", "").replace("-", "").isdigit():
                return float(data)
            
            # Si tu pesa tiene otro formato, modifica aquí
            else:
                print(f"Formato no reconocido: {data}")
                return None
                
        except (ValueError, IndexError):
            return None
    
    def process_queue(self):
        """Procesa los datos del hilo de monitoreo"""
        try:
            while True:
                item = self.data_queue.get_nowait()
                event_type, data = item
                
                if event_type == "peso":
                    self.actualizar_peso(data)
                elif event_type == "error":
                    messagebox.showerror("Error de Comunicación", data)
                    self.desconectar()
                
        except queue.Empty:
            pass
        
        # Reagendar para el próximo check
        self.root.after(100, self.process_queue)
    
    def actualizar_peso(self, peso):
        """Actualiza el display de peso y el historial"""
        self.peso_actual = peso
        self.peso_var.set(f"{peso:.2f}")
        
        # Agregar al historial textual
        timestamp = datetime.now().strftime("%H:%M:%S")
        entrada = f"{timestamp} - {peso:8.2f} kg"
        
        # Agregar al listbox
        self.historial_listbox.insert(0, entrada)  # Insertar al principio
        
        # Mantener solo las últimas 50 lecturas
        if self.historial_listbox.size() > 50:
            self.historial_listbox.delete(49)  # Eliminar la más antigua
        
        # Auto-scroll para mostrar la más reciente
        self.historial_listbox.see(0)
    
    def hacer_tara(self):
        """Envía comando de tara a la pesa"""
        if self.serial_connection:
            try:
                # Comando común de tara (ajusta según tu pesa)
                self.serial_connection.write(b'T\r\n')  # o el comando que use tu pesa
                messagebox.showinfo("Tara", "Comando de tara enviado")
            except Exception as e:
                messagebox.showerror("Error", f"Error al hacer tara: {e}")
    
    def guardar_peso(self):
        """Guarda el peso actual en la lista"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.tree.insert("", "end", values=(timestamp, f"{self.peso_actual:.2f}"))
    
    def exportar_datos(self):
        """Exporta las mediciones guardadas a un archivo JSON"""
        if len(self.tree.get_children()) == 0:
            messagebox.showwarning("Sin Datos", "No hay mediciones para exportar")
            return
        
        filename = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        
        if filename:
            try:
                datos = []
                for item in self.tree.get_children():
                    valores = self.tree.item(item)['values']
                    datos.append({
                        "timestamp": valores[0],
                        "peso_kg": float(valores[1])
                    })
                
                with open(filename, 'w', encoding='utf-8') as f:
                    json.dump(datos, f, indent=2, ensure_ascii=False)
                
                messagebox.showinfo("Éxito", f"Datos exportados a {filename}")
                
            except Exception as e:
                messagebox.showerror("Error", f"Error al exportar: {e}")

def main():
    root = tk.Tk()
    app = PesaUSBMonitor(root)
    
    # Manejar cierre de aplicación
    def on_closing():
        app.desconectar()
        root.destroy()
    
    root.protocol("WM_DELETE_WINDOW", on_closing)
    root.mainloop()

if __name__ == "__main__":
    main()