"""
ingreso_mensual = 5000

if ingreso_mensual > 1000:
    print ("estas bien en latinoamerica")
    
if ingreso_mensual > 10000:
    print ("estas bien en cualquier parte del mundo")

else:
    print ("sos pobre")

en este caso de arriba necesitamos condicionar de manera correcta, porque ganando
5000 no sos pobre...

elif == else_if
"""           
ingreso_mensual = 499

if ingreso_mensual > 4000:
    print ("estas bien en cualquier parte del mundo")
    
elif ingreso_mensual > 1000:
    print ("estas bien en argentina")
    
elif ingreso_mensual >500:
    print ("estas bien en venezuela")

else:
    print ("sos pobre")

#tambien se usan if y else anidados, que significa que van dentro de otros if