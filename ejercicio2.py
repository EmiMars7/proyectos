"""
QUEREMOS SABER EN BASE A TU INGRESO | SI TE ALCANZA O NO PARA VIVIR
TAMBIEN QUE DEVUELVA MENSAJES DIVERTIDOS Y SI ES POSIBLE QUE VAYA
MEMORIZANDO EN QUE SE GASTO Y TIRE LISTADO O TAL VEZ NO.... 
"""

ingreso = (int(input("¿cual es tu ingreso$ ")))

print (f"Genial, ahora sabemos que tu ingreso es ${ingreso}")

conf = (int(input("seguimos? 1=SI Y 0=NO  ")))
if conf == 1:
    print ("Excelente eleccion") 
elif conf == 0:
    print ("Te la creiste, ya me completas")
conf = (int(1))
sigue = conf

if sigue == 1:
    gasto = (int(input("¿cuanto es tu gasto al mes? $ ")))
    
elif sigue == 0:
    print ("no quiere seguir la señorita")

if gasto > 0:
    print (f"Bueno, esto es lo que te esta quedando, ${ingreso-gasto}")
else:
    print ("Hola Mundo!")
    

    