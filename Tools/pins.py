"""Station positions checked by hand, for stations the automatic matching in
build_tariffs.py cannot place (no named toll booth in OSM, or an ambiguous
exit number), or places wrongly.

Per grid: {station name as printed: value}. A value is a list of references,
whose points are averaged:
  "n123…"            an OSM node: a toll booth from Tools/data/osm_toll_booths.json
                     (the station is then placed by booths) or a motorway
                     junction from Tools/data/osm_motorway_junctions.json;
  "booth:Name"       every OSM toll booth with that name;
  "exit:A10:44"      the interchange numbered 44 on the A10 (it must be unique;
                     "exit:A10:44@lat,lon" picks the one nearest that point);
  [lat, lon]         an explicit position.
Or a single string:
  "same:grid:Name"   the position of that station of another grid (the same
                     place under another name);
  "virtual"          not a place on a route (it is priced as a toll point, or
                     is a tariff convention).
"""

PINS = {
    "atmb": {
        "Saint-Julien": ["n11264369966"],  # A40 exit 13 Saint-Julien-en-Genevois
        "Etrembières - Annemasse": ["n1110757713", "n7043179811"],  # A40 exit 14 Annemasse
        "Origine": [[45.900965, 6.860764]],  # Mont-Blanc tunnel toll plaza (French side)
        "Cluses-Ouest": ["booth:Péage de Scionzier"],  # exit 18, west of Cluses
        "Cluses-Est": ["booth:Péage Cluses Amont", "booth:Péage Cluses Aval", "booth:Péage Cluses Centre"],  # exit 19
        "Findrol": ["booth:Péage de Nangy"],  # Findrol / Scientrier share one row: the Nangy plaza
        "Scientrier": ["booth:Péage de Nangy"],
        "Le Fayet": ["exit:A40:22"],
        "Genève": "virtual",  # the Swiss border, 0 € from every station of the free section
        "Chatillon": "virtual",  # APRR/ATMB limit on the A40 between Sylans and Bellegarde: no exit, no booth;
                                 # APRR prices trips through it itself (SYLANS -> BELLEGARDE)
    },
    "sftrf": {  # A43 exits in Maurienne
        "St Pierre": ["n2188188165", "n612573928"],  # exit 25 Saint-Pierre-de-Belleville
        "Ste Marie": ["n21032841", "n60294409"],  # exit 26 Sainte-Marie-de-Cuines
        "St Jean": ["n2185654628"],  # exit 27 Saint-Jean-de-Maurienne
        "St Julien": ["n267165935"],  # exit 28 Saint-Julien-Mont-Denis
        "Modane": ["n1139898026", "n279888636"],  # exit 30 Modane
    },
    "alis": {
        "Alençon": ["booth:Alençon Nord"],
        "Broglie": ["booth:Broglie-Orbec"],
        "A13": ["n248867577"],  # A28/A13 junction
    },
    "arcour": {
        "Savigny sur Claris": ["booth:Savigny-sur-Clairis"],
        "Gondreville la Franche": ["n1808309613", "n457361469"],  # A19/A77 junction
        "Piffonds": ["n456719874", "n97733462"],  # A19/A6 junction near Courtenay
        "Chevilly": ["n456737416"],  # A19/A10 junction near Artenay
    },
    "alienor": {
        "Aire-sur-l'Adour centre": ["booth:Aire-sur-l'Adour Nord"],
        "Langon (A62)": ["n648626013", "n648626111"],  # A62/A65 junction
        "Pau (A64)": ["n1921056977"],  # A65/A64 junction
    },
    "alicorne": {  # A88 exits 11 to 15
        "Falaise Ouest": ["n712698030", "n27784198"],
        "Falaise sud": ["n987821573"],
        "Argentan sud": ["n270426632"],
        "Mortrée": ["n1014077869", "n229546977"],
    },
    "asf": {
        # Same station as another grid's, under another name
        "Amboise/Château-Renault": "same:aprr:AMBOISE CH.RENAULT",
        "Montreuil-Reims": "same:sanef:MONTREUIL-AUX-LIONS",  # A4 exit 19
        "Broglie ouest": "same:alis:Broglie",  # A28 exit 15 Broglie-Orbec
        "Chatenois sud": "same:cofiroute:CHATENOIS",
        "L’Isle-sur-le-Doubs": "same:cofiroute:L'ISLE-SUR-LE-DOUBS",
        "Longué": "same:cofiroute:LONGUE-JUMELLES",
        "Pont-d’Ain": "same:cofiroute:PONT D'AIN",
        "Sylans sud": "same:cofiroute:SYLANS",
        "Le Caloy": "same:alienor:Mont-de-Marsan",  # A65 exit 4, between Roquefort (3) and Aire-sur-Adour (6)
        "Péage de Tours centre": "same:cofiroute:TOURS CENTRE (SORIGNY)",  # A10 barrier before Sainte-Maure (25)
        "Péage de St-Christophe": "same:cofiroute:TOURS CENTRE (SAINT CHRISTOPHE)",
        "St-Romain-sur-Cher": "same:cofiroute:SAINT AIGNAN SUR CHER",  # A85 exit 12
        "Chémery": "same:cofiroute:SELLES SUR CHER",  # A85 exit 13
        "Villefranche-sur-Cher": "same:cofiroute:ROMORANTIN",  # A85 exit 14
        # Toll booths named like the station
        "Aire-sur-Adour nord": ["booth:Aire-sur-l'Adour Nord"],
        "Aire-sur-Adour sud": ["booth:Aire-sur-l'Adour Sud"],
        "Capbreton (demi-échangeur nord)": ["booth:Capbreton"],
        "Capbreton (demi-échangeur sud)": ["booth:Capbreton"],
        "Chaumont/Semoutiers": ["booth:Chaumont-Semoutiers"],
        "Châlons/La Veuve": ["booth:Châlons en Champagne-La Veuve"],
        "Châlons/Mourmelon": ["booth:Châlons en Champagne-La Veuve"],  # same exit, other direction
        "Dijon/Arc-sur- Tille": ["booth:Dijon-Arc-sur-Tille"],
        "Gondreville nord": ["booth:Gondreville"],
        "Gondreville sud": ["booth:Gondreville"],
        "Le Boulou (péage en système fermé)": ["n1742991342", "n1987610456", "n1987610457", "n1987610458"],
        "Péage d’Argentan": ["booth:Argentan"],  # A28/A88, between Sées (17) and Alençon nord (18)
        "Péage de Beaulieu-s.-Layon": ["booth:Péage de Beaulieu-sur-Layon"],
        "Péage de Biriatou": ["booth:Péage de Biriatou"],
        "Péage de Bénesse-Marenne": ["booth:Péage de Bénesse-Maremne"],
        "Péage de Corzé": ["booth:Péage de Corzé-Angers"],
        "Péage de Dijon/Crimolois": ["booth:Péage de Dijon-Crimolois"],
        "Péage de Lançon (Aix/Berre)": ["booth:Péage de Lançon"],
        "Péage de Montpellier St-Jean": ["n9893188259", "n9893188262"],  # A9, between St-Jean-de-Védas (32) and Sète (33)
        "Péage de Mussidan": ["n298601377", "n298601379", "n512632720", "n512645301"],  # A89 barrier at Mussidan est (13.1)
        "Péage de Toulouse nord/est": ["booth:Péage de Toulouse Nord"],  # one plaza on the A62; the tariff depends on
        "Péage de Toulouse nord/ouest": ["booth:Péage de Toulouse Nord"],  # the ring branch the trip comes from
        "Péage de Toulouse sud/est": ["booth:Péage de Toulouse Sud"],  # same on the A61
        "Péage de Toulouse sud/ouest": ["booth:Péage de Toulouse Sud"],
        "Péage de la Négresse": ["n1371313451", "n1371313452"],  # A63 main-line barrier at Biarritz
        "Biarritz (demi-échangeur nord)": ["n1371313449", "n8897755575"],  # booths on the Biarritz ramps
        "Biarritz (demi-échangeur sud)": ["n1371313449", "n8897755575"],
        "Péage des Martres-d’Artière": ["booth:Péage des Martres-d'Artière"],
        "Péage du Roumois": ["booth:Péage du Roumois"],
        "Péage d’Arles": ["booth:Péage d'Arles"],
        "Péage d’Arveyres": ["booth:Péage d'Arveyres"],
        "Salon nord": ["n1457800884", "n308235934"],
        "St-Martin-de-Crau est": ["exit:A54:12"],
        "Tarare est (péage en système fermé)": ["n4422924492", "n4422924495"],
        # Interchanges by road and exit number (road from the order of the ASF charts)
        "Aix ouest": ["exit:A8:29"],
        "Ambes": ["exit:A10:41"],
        "Ambarès/St-Loubes": ["exit:A10:42"],
        "Sainte-Eulalie": ["exit:A10:43"],
        "Carbon-Blanc": ["exit:A10:44"],
        "Lormont": ["exit:A10:45"],
        "Libourne/St-Antoine": ["exit:A10:39a", "n21462856"],  # 39a and 39b, after the Virsac barrier
        "Blaye": ["exit:A10:40.a"],
        "St-Jean-d’Angély": ["exit:A10:34"],
        "Andrézieux-Bouthéon nord": ["exit:A72:8"],
        "Andrézieux-Bouthéon sud": ["exit:A72:8"],
        "La Fouillouse": ["exit:A72:9"],
        "Brive ouest": ["exit:A89:19"],
        "Libourne ouest": ["exit:A89:9"],
        "Thenon est": ["exit:A89:17"],
        "L’Arbresle": ["exit:A89:36"],
        "Pont de Dorieux": ["exit:A89:37"],
        "Lentilly": ["exit:A89:38"],
        "Chasse sud": ["exit:A7:8"],
        "Vienne nord": ["exit:A7:9"],
        "Vienne sud": ["exit:A7:11"],
        "Rognac Berre": ["exit:A7:28"],
        "Fort de St-Priest": ["exit:A46:11"],
        "Mions": ["exit:A46:13"],
        "Vénissieux": ["exit:A46:14"],
        "Marennes": ["exit:A46:15"],
        "Communay": ["exit:A46:16"],
        # Angers (A11 / A87): Pellouailles 13 … Mûrs-Érigné 23
        "Pellouailles-les-Vignes": ["exit:A11:13"],
        "Gatignolle": ["exit:A11:14"],
        "RD 323": ["exit:A87N:15"],
        "La Bouvinerie": ["exit:A87N:16"],
        "RD 347": ["exit:A87N:17"],
        "Hanipet": ["exit:A87N:18a"],
        "Bd d’Estienne d’Orves": ["exit:A87N:18b"],
        "La Foucaudière": ["exit:A87N:19"],
        "La Monnaie": ["exit:A87N:20"],
        "Sorges": ["exit:A87N:21"],
        "Haute-Perche": ["exit:A87N:22"],
        "Mûrs-Érigné": ["exit:A87:23"],
        "La Roche-sur-Yon est": ["exit:A87:30"],
        "La Roche-sur-Yon centre": ["exit:A87:31"],
        "La Roche-sur-Yon sud": ["exit:A87:32"],
        "La Roche-sur-Yon ouest": ["exit:A87:33"],
        "Le Mans nord": ["exit:A11:7"],
        "Thivars": ["exit:A11:3"],
        "Luigny": ["exit:A11:4"],
        "Rochefort ouest": ["exit:A837:31"],
        "Rochefort nord": ["exit:A837:32"],
        "Tonnay-Charente (sortie 33)": ["exit:A837:33"],
        "Tonnay-Charente (sortie 34)": ["exit:A837:34"],
        "Val de Loing/Souppes": ["exit:A77:17"],
        # Toulouse and the south-west
        "L’Union": ["exit:A68:1"],
        "Montastruc": ["exit:A68:3"],
        "La Croix Daurade": ["exit:A62:14"],
        "Valence-d’Agen": ["exit:A62:8"],
        "Roques": ["exit:A64:36"],
        "Francazal": ["exit:A64:37"],
        "Mousserolles": ["exit:A64:1"],
        "Mouguerre Elizaberry": ["exit:A64:2"],
        "St-Geours-de-Maremne": ["exit:A63:9"],
        "Pamiers Sud": ["exit:A66:4"],
        "Montauban nord": ["exit:A20:60"],
        "ZI nord": ["exit:A20:61"],
        "Chaumes": ["exit:A20:62"],
        "Moulis": ["exit:A20:67"],  # A20, between Parages (66) and Montauban (A62 exit 10)
        "Nespouls": ["exit:A20:53"],
        "Vendargues": ["exit:A709:28"],
        "Bretelle de Verfeil": [[43.6886, 1.5689]],  # where the A69 "Bretelle de Verfeil" leaves the A68
    },
    "aprr": {
        # Stations of neighbouring networks, under APRR's names
        "CHALONS MOURMELON": ["booth:Châlons en Champagne-La Veuve"],  # A4 exit 27, Mourmelon direction
        "CHEMERY": "same:cofiroute:SELLES SUR CHER",  # A85 exit 13
        "GONDREVILLE A77/N": ["booth:Gondreville"],  # A19 exit 6, towards the A77 north
        "GONDREVILLE A77/S": ["booth:Gondreville"],  # same plaza, towards the A77 south
        "LA FOLIE-B/PARIS": ["booth:Péage de Saint-Arnoult"],  # A10 barrier at La Folie-Bessin
        "LES EPRUNES": ["booth:Péage des Eprunes"],
        "MONTREUIL (REIMS)": "same:asf:Péage de Montreuil-aux-Lions",  # A4 barrier (exit 19 is MONTREUIL AUX LIONS)
        "REIMS EST (TAISSY)": ["booth:Péage de Reims Est"],
        "REIMS NORD (ORMES)": ["booth:Péage de Reims Nord "],
        "REIMS OUEST (THILLOIS)": ["booth:Péage de Reims Ouest"],
        "ST GERMAIN LES VERGNE": "same:cofiroute:ST GERMAIN LES VERGNES",
        "ST HILAIRE": "same:cofiroute:SAINT HILAIRE LES ANDRESIS",  # 5 km from Courtenay in the grid
        "ST ROMAIN SUR CHER": "same:cofiroute:SAINT AIGNAN SUR CHER",  # A85 exit 12
        "TOURS-C/MONNAIE": "same:asf:Péage de Monnaie",
        "VILLE SOUS LAFERTE": "same:cofiroute:VILLE SOUS LA FERTE",
        "VILLEFRANCHE S/ CHER": "same:cofiroute:ROMORANTIN",  # A85 exit 14
        "LUSSE": "virtual",  # the Maurice-Lemaire tunnel toll (same 6,80 €), priced by the toll point "tml"
    },
    "aliae": {  # the ALIAE grid prints the same stations under the same names as APRR
        # Stations of neighbouring networks, under APRR's names
        "CHALONS MOURMELON": ["booth:Châlons en Champagne-La Veuve"],  # A4 exit 27, Mourmelon direction
        "CHEMERY": "same:cofiroute:SELLES SUR CHER",  # A85 exit 13
        "GONDREVILLE A77/N": ["booth:Gondreville"],  # A19 exit 6, towards the A77 north
        "GONDREVILLE A77/S": ["booth:Gondreville"],  # same plaza, towards the A77 south
        "LA FOLIE-B/PARIS": ["booth:Péage de Saint-Arnoult"],  # A10 barrier at La Folie-Bessin
        "LES EPRUNES": ["booth:Péage des Eprunes"],
        "MONTREUIL (REIMS)": "same:asf:Péage de Montreuil-aux-Lions",  # A4 barrier (exit 19 is MONTREUIL AUX LIONS)
        "REIMS EST (TAISSY)": ["booth:Péage de Reims Est"],
        "REIMS NORD (ORMES)": ["booth:Péage de Reims Nord "],
        "REIMS OUEST (THILLOIS)": ["booth:Péage de Reims Ouest"],
        "ST GERMAIN LES VERGNE": "same:cofiroute:ST GERMAIN LES VERGNES",
        "ST HILAIRE": "same:cofiroute:SAINT HILAIRE LES ANDRESIS",  # 5 km from Courtenay in the grid
        "ST ROMAIN SUR CHER": "same:cofiroute:SAINT AIGNAN SUR CHER",  # A85 exit 12
        "TOURS-C/MONNAIE": "same:asf:Péage de Monnaie",
        "VILLE SOUS LAFERTE": "same:cofiroute:VILLE SOUS LA FERTE",
        "VILLEFRANCHE S/ CHER": "same:cofiroute:ROMORANTIN",  # A85 exit 14
    },
    "cofiroute": {
        "ANGERS (CORZE)": ["booth:Péage de Corzé-Angers"],
        # The guide prints ANGERS with the other station's exit number ("A11 20 ANCENIS -
        # A11 20 ANGERS"), which placed it at Ancenis. It is the A11 west of Angers,
        # just before Saint-Jean-de-Linières (18, 0,60 €).
        "ANGERS": ["exit:A11:17"],
        "BARRIERE DE MONTREUIL AUX LIONS": "same:asf:Péage de Montreuil-aux-Lions",
        "CHALONS - LA VEUVE": ["booth:Châlons en Champagne-La Veuve"],  # was matched to a wrong exit 27
        "CRIMOLOIS": ["booth:Péage de Dijon-Crimolois"],
        "GONDREVILLE LA FRANCHE NORD": ["booth:Gondreville"],
        "GONDREVILLE LA FRANCHE SUD": ["booth:Gondreville"],
        "LE BIGNON": ["booth:Péage du Bignon"],
        "LES EPRUNES": ["booth:Péage des Eprunes"],
        "ORMES": ["booth:Péage de Reims Nord "],
        "PARIS (LA FOLIE BESSIN)": ["booth:Péage de Saint-Arnoult"],
        "REIMS - TAISSY": ["booth:Péage de Reims Est"],
        "ROUMOIS": ["booth:Péage du Roumois"],
        "TOURS CENTRE (MONNAIE)": "same:asf:Péage de Monnaie",
        "VITRE (LA GRAVELLE)": ["booth:Péage de La Gravelle"],
        "BEAULIEU": ["booth:Péage de Beaulieu-sur-Layon"],  # printed "A87 - BEAULIEU"
        "DRUYE (CANDE)": ["exit:A85:9"],  # A85 at Druye, the last access before the Candé plaza (2,10 €)
    },
    "adelac": {
        "BPV Villy-le-Pelloux": ["n505681", "n505680"],  # main-line barrier (A41, Saint-Martin-Bellevue)
        "BSE Nord": ["n4423745205", "n4423745204"],  # half-interchange of Cruseilles (A41 north)
    },
    "escota": {
        "Aix (A51)": ["exit:A51:14"],  # free A51 north of Aix, before the Pertuis plaza
        "Aix (A57, A50, A52, A8)": ["exit:A8:31"],  # A8 east of Aix, before La Barque
        "Beausoleil/ Monaco Est": ["exit:A8:58@43.751,7.41"],
        "Cannet-de-Meyreuil": ["booth:Canet de Meyreuil"],
        "Gémenos": ["exit:A52:34"],
        "La Bédoule": ["exit:A50:7"],
        "St-Cyr-Les Lecques": ["exit:A50:10"],
        "La Cadière": ["exit:A50:11"],
        "Six-Fours-Les Plages": ["exit:A50:13"],
        "Toulon-ouest": ["exit:A50:15"],
    },
    "sanef": {
        "AMIENS EST (péage de Jules Verne)": ["booth:Péage de Jules Verne"],
        "AMIENS SUD (péage de Dury)": ["booth:Péage de Dury"],
        "ARRAS EST (A1)": ["booth:Arras Est"],
        "ARRAS NORD (A26)": ["booth:Arras Nord"],
        "BOULOGNE EST (péage d'Herquelingue)": ["booth:Péage d'Herquelingue"],
        "CALAIS (péage de Setques)": ["booth:Péage de Setques"],
        "CAMBRAI": ["booth:Cambrai Ouest"],  # A2 exit 14
        "MARQUION": ["booth:Cambrai - Marquion"],  # A26 exit 8
        "FREYMING-MERLEBACH (A320)": ["exit:A4:38"],  # A4/A320
        "HORDAIN (péage d'Hordain)": ["booth:Péage de Thun l'Évêque"],  # A2 barrier, 1,20 € from Cambrai
        "L'ISLE-ADAM (péage d'Amblainville)": ["booth:Péage d'Amblainville"],
        "LILLE / DOURGES (péage de Fresnes)": ["booth:Péage de Fresnes"],
        "MEAUX (A140) / CRECY": ["exit:A4:16"],
        "METZ (A31)": ["n30802017", "n1524472678"],  # A4 at the A31 interchange, between exits 34 and 35
        "NEUFCHÂTEL-EN-BRAY (A28)": ["n32628328", "n5804845185"],  # A29/A28 interchange
        "PARIS / NOISY-LE-GRAND (péage de Coutevroult)": ["booth:Coutevroult"],
        "PARIS / ROISSY (péage de Chamant)": ["booth:Péage de Chamant"],
        "PÉRONNE / VALLEE DE LA SOMME": ["booth:Péronne-Vallée de la Somme"],
        "REIMS (péage de Courcy)": ["booth:Péage de Courcy"],
        "REIMS EST (péage de Taissy)": ["booth:Péage de Reims Est"],
        "REIMS NORD (péage d'Ormes)": ["booth:Péage de Reims Nord "],
        "REIMS OUEST (péage de Thillois)": ["booth:Péage de Reims Ouest"],
        "STRASBOURG": ["booth:Péage de Schwindratzheim"],  # last A4 barrier, 1,40 € from Hochfelden
        "SURVILLIERS / SAINT-WITZ": ["booth:Survilliers-saint witz"],
    },
    "sapn": {
        "BEAUTOT / A151": ["booth:Beautot"],
        "BONNIÈRES-SUR-SEINE (A13a)": ["n1472404850"],
        "CAEN": ["booth:Cagny"],  # same price as Cagny from every station: the A13 end at Caen
        "CAGNY (A813)": ["booth:Cagny"],
        "CHAUFOUR N°15 à GAILLON N°17": ["exit:A13:15", "exit:A13:16", "exit:A13:17"],
        "CHENARD N°1 (A29)": ["exit:A29:1"],
        "CRIQUEBEUF N°20 à MAISON-BRÛLEE N°24 / ROUEN LES ESSARTS (A139)":
            ["exit:A13:20", "exit:A13:21", "exit:A13:22", "exit:A13:23", "exit:A13:24"],
        "INCARVILLE N°19 / A154": ["booth:Incarville"],
        "LA RIVIÈRE-SAINT-SAUVEUR N°3 (A29)": ["exit:A29:3"],
        "LE HAVRE N°5 / A131": ["exit:A29:5"],
        "PLATEAU N°2 (A29)": ["booth:Plateau"],
        "POISSY / ORGEVAL N°7 à MANTES-SUD N°12":
            ["exit:A13:7", "exit:A13:8", "exit:A13:9", "exit:A13:10", "exit:A13:11", "exit:A13:12"],
        "PONT L'EVÊQUE, DEAUVILLE (A132)": ["n374147126"],
        "ST-SAËNS N°10 / A28": ["booth:Saint-Saens"],
        "TANCARVILLE (A131)": ["n25554977"],  # A13/A131 interchange, from the Tancarville bridge
        "YVETOT / A150": ["booth:Yvetot"],
    },
}
