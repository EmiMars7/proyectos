#datos compuestos perro

#LISTAS (se pueden modificar)

lista = ["Emiliano Marsilli","27 años", "super fachero"] #lleva corchetes

print (lista)   #se cuenta del 0 al 9 ¿sabes?
print (lista[0]) #deberia devolver nombre y apellido


#TUPLAS /// Como una lista, pero no se puede modificar

tupla = ("Emiliano Marsilli", "27 años","super fachero") #lleva parentesis

#tupla[0] = "sabina"    no te va a dejar porque es una "tupla"

print (tupla)

#CONJUNTO///   (set)

conjunto = {"Emiliano Marsilli", "27 años","super fachero"} #lleva llave / no puede haber duplicados


#DICCIONARIO se le compara a un JSON  en JAVASCRIPT  "dict"

diccionario = {
 "nombre" : "Emiliano Marsilli",
 "habilidad" : "Developer Expert",
 "Moto" : True,
 "altura" : 1.80
}

print (diccionario["nombre"])
