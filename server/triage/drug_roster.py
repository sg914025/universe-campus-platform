"""中文常用西药检索目录；不含剂量、处方或可用性保证。标签以导入源为准。"""
ROSTER_TEXT = '''
解热镇痛|对乙酰氨基酚|acetaminophen
解热镇痛|布洛芬|ibuprofen
解热镇痛|萘普生|naproxen
解热镇痛|双氯芬酸|diclofenac
解热镇痛|塞来昔布|celecoxib
解热镇痛|美洛昔康|meloxicam
解热镇痛|吲哚美辛|indomethacin
解热镇痛|依托度酸|etodolac
抗感染|阿莫西林|amoxicillin
抗感染|氨苄西林|ampicillin
抗感染|青霉素V|penicillin v potassium
抗感染|头孢氨苄|cephalexin
抗感染|头孢呋辛|cefuroxime
抗感染|头孢克肟|cefixime
抗感染|头孢地尼|cefdinir
抗感染|头孢泊肟|cefpodoxime
抗感染|阿奇霉素|azithromycin
抗感染|克拉霉素|clarithromycin
抗感染|红霉素|erythromycin
抗感染|多西环素|doxycycline
抗感染|米诺环素|minocycline
抗感染|克林霉素|clindamycin
抗感染|甲硝唑|metronidazole
抗感染|替硝唑|tinidazole
抗感染|左氧氟沙星|levofloxacin
抗感染|环丙沙星|ciprofloxacin
抗感染|莫西沙星|moxifloxacin
抗感染|呋喃妥因|nitrofurantoin
抗感染|磷霉素|fosfomycin
抗感染|利福平|rifampin
抗感染|异烟肼|isoniazid
抗感染|乙胺丁醇|ethambutol
抗感染|吡嗪酰胺|pyrazinamide
抗病毒|阿昔洛韦|acyclovir
抗病毒|伐昔洛韦|valacyclovir
抗病毒|泛昔洛韦|famciclovir
抗病毒|奥司他韦|oseltamivir
抗病毒|扎那米韦|zanamivir
抗病毒|恩替卡韦|entecavir
抗病毒|替诺福韦|tenofovir disoproxil fumarate
抗真菌|氟康唑|fluconazole
抗真菌|伊曲康唑|itraconazole
抗真菌|伏立康唑|voriconazole
抗真菌|特比萘芬|terbinafine
抗真菌|克霉唑|clotrimazole
抗真菌|咪康唑|miconazole
抗真菌|制霉菌素|nystatin
消化系统|奥美拉唑|omeprazole
消化系统|埃索美拉唑|esomeprazole
消化系统|泮托拉唑|pantoprazole
消化系统|兰索拉唑|lansoprazole
消化系统|雷贝拉唑|rabeprazole
消化系统|法莫替丁|famotidine
消化系统|西咪替丁|cimetidine
消化系统|硫糖铝|sucralfate
消化系统|氢氧化铝|aluminum hydroxide
消化系统|氢氧化镁|magnesium hydroxide
消化系统|碳酸钙|calcium carbonate
消化系统|西甲硅油|simethicone
消化系统|洛哌丁胺|loperamide
消化系统|乳果糖|lactulose
消化系统|聚乙二醇|polyethylene glycol 3350
消化系统|比沙可啶|bisacodyl
消化系统|多库酯钠|docusate sodium
消化系统|番泻苷|sennosides
消化系统|昂丹司琼|ondansetron
消化系统|甲氧氯普胺|metoclopramide
消化系统|美沙拉嗪|mesalamine
消化系统|胰酶|pancrelipase
消化系统|熊去氧胆酸|ursodiol
过敏与呼吸|氯雷他定|loratadine
过敏与呼吸|西替利嗪|cetirizine
过敏与呼吸|左西替利嗪|levocetirizine
过敏与呼吸|非索非那定|fexofenadine
过敏与呼吸|地氯雷他定|desloratadine
过敏与呼吸|氯苯那敏|chlorpheniramine
过敏与呼吸|苯海拉明|diphenhydramine
过敏与呼吸|羟嗪|hydroxyzine
过敏与呼吸|孟鲁司特|montelukast
过敏与呼吸|沙丁胺醇|albuterol
过敏与呼吸|左旋沙丁胺醇|levalbuterol
过敏与呼吸|异丙托溴铵|ipratropium
过敏与呼吸|噻托溴铵|tiotropium
过敏与呼吸|布地奈德|budesonide
过敏与呼吸|氟替卡松|fluticasone
过敏与呼吸|莫米松|mometasone
过敏与呼吸|倍氯米松|beclomethasone
过敏与呼吸|茶碱|theophylline
过敏与呼吸|右美沙芬|dextromethorphan
过敏与呼吸|愈创甘油醚|guaifenesin
过敏与呼吸|乙酰半胱氨酸|acetylcysteine
心血管|氨氯地平|amlodipine
心血管|硝苯地平|nifedipine
心血管|非洛地平|felodipine
心血管|地尔硫卓|diltiazem
心血管|维拉帕米|verapamil
心血管|贝那普利|benazepril
心血管|依那普利|enalapril
心血管|赖诺普利|lisinopril
心血管|卡托普利|captopril
心血管|雷米普利|ramipril
心血管|氯沙坦|losartan
心血管|缬沙坦|valsartan
心血管|厄贝沙坦|irbesartan
心血管|替米沙坦|telmisartan
心血管|坎地沙坦|candesartan
心血管|奥美沙坦|olmesartan
心血管|美托洛尔|metoprolol
心血管|比索洛尔|bisoprolol
心血管|阿替洛尔|atenolol
心血管|卡维地洛|carvedilol
心血管|普萘洛尔|propranolol
心血管|氢氯噻嗪|hydrochlorothiazide
心血管|吲达帕胺|indapamide
心血管|呋塞米|furosemide
心血管|螺内酯|spironolactone
心血管|依普利酮|eplerenone
心血管|硝酸甘油|nitroglycerin
心血管|单硝酸异山梨酯|isosorbide mononitrate
心血管|地高辛|digoxin
心血管|胺碘酮|amiodarone
心血管|索他洛尔|sotalol
心血管|阿司匹林|aspirin
心血管|氯吡格雷|clopidogrel
心血管|替格瑞洛|ticagrelor
心血管|华法林|warfarin
心血管|利伐沙班|rivaroxaban
心血管|阿哌沙班|apixaban
心血管|达比加群|dabigatran
心血管|阿托伐他汀|atorvastatin
心血管|瑞舒伐他汀|rosuvastatin
心血管|辛伐他汀|simvastatin
心血管|普伐他汀|pravastatin
心血管|非诺贝特|fenofibrate
心血管|依折麦布|ezetimibe
内分泌代谢|二甲双胍|metformin
内分泌代谢|格列吡嗪|glipizide
内分泌代谢|格列美脲|glimepiride
内分泌代谢|格列本脲|glyburide
内分泌代谢|瑞格列奈|repaglinide
内分泌代谢|吡格列酮|pioglitazone
内分泌代谢|西格列汀|sitagliptin
内分泌代谢|利格列汀|linagliptin
内分泌代谢|恩格列净|empagliflozin
内分泌代谢|达格列净|dapagliflozin
内分泌代谢|卡格列净|canagliflozin
内分泌代谢|阿卡波糖|acarbose
内分泌代谢|司美格鲁肽|semaglutide
内分泌代谢|利拉鲁肽|liraglutide
内分泌代谢|度拉糖肽|dulaglutide
内分泌代谢|甘精胰岛素|insulin glargine
内分泌代谢|门冬胰岛素|insulin aspart
内分泌代谢|赖脯胰岛素|insulin lispro
内分泌代谢|左甲状腺素|levothyroxine
内分泌代谢|甲巯咪唑|methimazole
内分泌代谢|丙硫氧嘧啶|propylthiouracil
内分泌代谢|别嘌醇|allopurinol
内分泌代谢|非布司他|febuxostat
内分泌代谢|秋水仙碱|colchicine
内分泌代谢|阿仑膦酸|alendronate
内分泌代谢|利塞膦酸|risedronate
皮肤与炎症|氢化可的松|hydrocortisone
皮肤与炎症|泼尼松|prednisone
皮肤与炎症|泼尼松龙|prednisolone
皮肤与炎症|甲泼尼龙|methylprednisolone
皮肤与炎症|地塞米松|dexamethasone
皮肤与炎症|倍他米松|betamethasone
皮肤与炎症|曲安奈德|triamcinolone
皮肤与炎症|他克莫司|tacrolimus
皮肤与炎症|吡美莫司|pimecrolimus
皮肤与炎症|莫匹罗星|mupirocin
皮肤与炎症|过氧苯甲酰|benzoyl peroxide
皮肤与炎症|阿达帕林|adapalene
皮肤与炎症|维A酸|tretinoin
皮肤与炎症|异维A酸|isotretinoin
眼耳鼻|人工泪液羧甲基纤维素|carboxymethylcellulose sodium
眼耳鼻|奥洛他定|olopatadine
眼耳鼻|酮替芬|ketotifen
眼耳鼻|拉坦前列素|latanoprost
眼耳鼻|噻吗洛尔|timolol
眼耳鼻|溴莫尼定|brimonidine
眼耳鼻|多佐胺|dorzolamide
眼耳鼻|阿司氮卓|azelastine
眼耳鼻|羟甲唑啉|oxymetazoline
泌尿与妇科|坦索罗辛|tamsulosin
泌尿与妇科|非那雄胺|finasteride
泌尿与妇科|度他雄胺|dutasteride
泌尿与妇科|索利那新|solifenacin
泌尿与妇科|奥昔布宁|oxybutynin
泌尿与妇科|米拉贝隆|mirabegron
泌尿与妇科|孕酮|progesterone
泌尿与妇科|雌二醇|estradiol
精神神经|舍曲林|sertraline
精神神经|氟西汀|fluoxetine
精神神经|帕罗西汀|paroxetine
精神神经|西酞普兰|citalopram
精神神经|艾司西酞普兰|escitalopram
精神神经|文拉法辛|venlafaxine
精神神经|度洛西汀|duloxetine
精神神经|米氮平|mirtazapine
精神神经|阿米替林|amitriptyline
精神神经|曲唑酮|trazodone
精神神经|丙戊酸|valproic acid
精神神经|卡马西平|carbamazepine
精神神经|奥卡西平|oxcarbazepine
精神神经|拉莫三嗪|lamotrigine
精神神经|左乙拉西坦|levetiracetam
精神神经|托吡酯|topiramate
精神神经|多奈哌齐|donepezil
精神神经|美金刚|memantine
精神神经|利培酮|risperidone
精神神经|奥氮平|olanzapine
精神神经|喹硫平|quetiapine
维生素与其他|叶酸|folic acid
维生素与其他|维生素B1|thiamine
维生素与其他|维生素B6|pyridoxine
维生素与其他|维生素B12|cyanocobalamin
维生素与其他|维生素C|ascorbic acid
维生素与其他|维生素D|cholecalciferol
维生素与其他|骨化三醇|calcitriol
维生素与其他|硫酸亚铁|ferrous sulfate
维生素与其他|葡萄糖酸亚铁|ferrous gluconate
维生素与其他|氯化钾|potassium chloride
'''


def roster():
    return [{'category':category,'name':name,'english':english,'id':english.replace(' ','_')}
            for category,name,english in (line.split('|') for line in ROSTER_TEXT.strip().splitlines())]
