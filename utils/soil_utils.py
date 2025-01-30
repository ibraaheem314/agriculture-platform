def analyze_soil(soil_type):
    if soil_type == "sandy":
        return "Votre sol est sablonneux. Ajoutez plus d'eau et utilisez des engrais organiques."
    elif soil_type == "clay":
        return "Votre sol est argileux. Assurez-vous de bien drainer avant de planter."
    else:
        return "Type de sol inconnu. Consultez un expert pour une analyse complète."