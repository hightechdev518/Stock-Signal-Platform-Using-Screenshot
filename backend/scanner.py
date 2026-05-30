"""
Stock scanner — fetches top gainers, losers, most active
with quick BUY/SELL/HOLD signal for each ticker.
"""

import pandas as pd
import yfinance as yf
from concurrent.futures import ThreadPoolExecutor, as_completed

from yfinance_setup import configure_yfinance_cache, safe_ticker_history

import json
import threading
import time
import time as _time
from pathlib import Path

_APP_DATA = Path.home() / "AppData" / "Roaming" / "stock-signal-dashboard"
METADATA_PATH = _APP_DATA / "ticker_metadata.json"
TICKER_LIST_PATH = _APP_DATA / "ticker_list.json"

_scanner_cache: list[dict] = []
_scanner_cache_lock = threading.Lock()
_scanner_cache_ready = threading.Event()
_scanner_last_updated: float = 0.0
_scan_complete = False

# Predefined ticker lists
LARGE_CAPS = [
    "AAPL", "MSFT", "GOOGL", "AMZN", "TSLA",
    "NVDA", "META", "JPM", "JNJ", "WMT",
    "XOM", "V", "UNH", "PG", "MA",
]
MID_CAPS = [
    "SAIC", "PLTR", "COIN", "INTC",
    "MSTR", "GME", "AMC", "SNAP", "UBER",
]
PENNY_STOCKS = [
    "OCGN", "SNDL", "CENN", "SLXN",
    "GRAN", "XSLL", "WKHS",
]
ALL_TICKERS = [
    "AAL", "AAP", "AAWW", "ABG", "ABM", "ACC", "ACM", "ACMR", "ACT", "ADNT",
    "AEO", "AFG", "AGCO", "AGO", "AGR", "AHH", "AHL", "AIT", "AIZ", "AKR",
    "AL", "ALG", "ALGT", "ALK", "ALL", "ALKS", "ALV", "AM", "AMBC", "AMC",
    "AMCX", "AMG", "AMP", "AMR", "AMWD", "AN", "ANET", "ANF", "ANH", "ANN",
    "AON", "AOS", "AP", "APA", "APG", "APH", "APLE", "APO", "AR", "ARC",
    "ARCO", "ARE", "ARGO", "ARI", "ARR", "ASB", "ASGN", "ASH", "ASO", "ASR",
    "ASTE", "AT", "ATO", "ATR", "AUB", "AVA", "AVAV", "AVT", "AWI", "AWK",
    "AXS", "AZZ", "B", "BCC", "BCO", "BDC", "BDN", "BEN", "BFH", "BGS",
    "BHC", "BHF", "BIG", "BIO", "BJ", "BKH", "BKU", "BL", "BLKB", "BMI",
    "BMS", "BMY", "BNL", "BOH", "BOX", "BRC", "BRX", "BSM", "BV", "BW",
    "BWA", "BXC", "BXP", "BY", "BYD", "CABO", "CACI", "CAKE", "CALM", "CAMT",
    "CAR", "CARS", "CASH", "CASY", "CATO", "CAVA", "CBRL", "CBT", "CBU",
    "CCOI", "CDK", "CDNS", "CDP", "CDW", "CE", "CFR", "CG", "CGNX", "CHE",
    "CHGG", "CHH", "CHL", "CHRD", "CHRS", "CHRW", "CHS", "CHX", "CIEN",
    "CIR", "CIVI", "CKH", "CL", "CLAR", "CLB", "CLDX", "CLF", "CLI", "CLW",
    "CMC", "CMCO", "CMO", "CMP", "CNK", "CNO", "CNX", "COKE", "COLB", "COLD",
    "COMM", "CONE", "CONN", "COOP", "COR", "CORT", "COTY", "CPE", "CPF",
    "CPK", "CPRI", "CRC", "CRK", "CROX", "CRS", "CRY", "CSL", "CSWI", "CTB",
    "CTLT", "CTRE", "CTS", "CUZ", "CVX", "CVBF", "CW", "CWT", "CXM", "CXW",
    "CYTOQ", "DAN", "DAR", "DBRG", "DCO", "DD", "DDS", "DEA", "DFS", "DIN",
    "DKS", "DLB", "DLX", "DNB", "DNOW", "DO", "DOC", "DRH", "DRI", "DRVN",
    "DSP", "DT", "DV", "DVA", "DXPE", "DY", "EAT", "EBC", "EFC", "EGP",
    "EHC", "ELF", "ELFK", "ELS", "ELVT", "EME", "EPC", "EPR", "EPRT", "EQC",
    "EQT", "ERII", "ESE", "ESNT", "ESS", "ESTA", "EVR", "EWC", "EXEL", "EXP",
    "EXPD", "EXPI", "EXR", "FAST", "FBIN", "FBP", "FCNCA", "FCF", "FELE",
    "FHI", "FHN", "FI", "FISI", "FL", "FLO", "FLS", "FNB", "FNF", "FORM",
    "FOUR", "FR", "FUL", "FULT", "G", "GBX", "GEF", "GFF", "GHC", "GKOS",
    "GL", "GLNG", "GME", "GMS", "GNL", "GNW", "GPOR", "GRC", "GRFS", "GRI",
    "GVA", "H", "HAE", "HASI", "HAYW", "HBI", "HBIO", "HCC", "HCI", "HE",
    "HEES", "HGV", "HIW", "HLF", "HMN", "HNI", "HOG", "HOPE", "HP", "HPP",
    "HQY", "HR", "HRI", "HRB", "HSII", "HTH", "HUN", "HWC", "IBP", "ICL",
    "IDCC", "IESC", "IGT", "INN", "INVA", "INVEST", "IP", "IPG", "IRT",
    "ITGR", "JACK", "JBGS", "JBLU", "JELD", "JHG", "JLL", "JOE", "JOBY",
    "JOUT", "JWN", "KBH", "KBR", "KFY", "KGS", "KMT", "KN", "KNF", "KNX",
    "KOP", "KRC", "KRG", "KSS", "KTB", "KW", "LADR", "LAZ", "LBC", "LCII",
    "LEN", "LGF", "LGO", "LII", "LIVN", "LKQ", "LMAT", "LNC", "LNN", "LPX",
    "LRN", "LSCC", "LTC", "LW", "M", "MAC", "MAN", "MATX", "MBC", "MBI",
    "MCS", "MDU", "MED", "MEDP", "MEI", "MFA", "MHK", "MHO", "MKL", "MLI",
    "MMI", "MMS", "MNR", "MOG", "MPW", "MRC", "MRCY", "MRP", "MSA", "MSM",
    "MTG", "MTH", "MTUS", "MUR", "MYRG", "NAD", "NARI", "NBR", "NBTB", "NEP",
    "NEU", "NFG", "NFBK", "NHI", "NI", "NJR", "NNN", "NOG", "NPO", "NRC",
    "NRG", "NRP", "NSA", "NSP", "NUE", "NUS", "NVR", "NVT", "NWE", "NWL",
    "NWN", "ODP", "OFG", "OGE", "OGS", "OHI", "OII", "OIS", "OLN", "OMF",
    "ONB", "OPK", "OPRX", "ORI", "OTTR", "OUT", "OXM", "PAHC", "PARR",
    "PATK", "PBF", "PBFX", "PBH", "PCAR", "PCH", "PDM", "PDCO", "PEB",
    "PECO", "PEN", "PENN", "PES", "PFC", "PII", "PINC", "PKG", "POR", "POST",
    "POWL", "PRGO", "PRIM", "PRK", "PRMW", "PRO", "PRSC", "PSA", "PSMT",
    "PTVE", "PVH", "PZZA", "RBC", "RCHC", "RCL", "RCM", "RCUS", "RDN",
    "RES", "REX", "REXR", "RGP", "RIG", "RLAY", "RLI", "RLJ", "RMD", "RMR",
    "RNG", "RNST", "RNW", "RPM", "RRR", "RS", "RXO", "SAFE", "SAIA", "SANM",
    "SBH", "SBR", "SBRA", "SCI", "SCSC", "SEE", "SFM", "SFNC", "SHO", "SIG",
    "SJW", "SKT", "SLG", "SM", "SMAR", "SMG", "SMP", "SNV", "SO", "SONO",
    "SPB", "SPTN", "SRI", "SSB", "SSBK", "STC", "STEP", "STL", "STNG",
    "STOR", "SUM", "SWI", "SWK", "SWX", "SXI", "SXT", "SYF", "SYKE", "SYM",
    "TALO", "TDC", "TDS", "TENB", "TGI", "TGS", "TH", "THG", "THO", "TILE",
    "TKR", "TMP", "TNL", "TOWN", "TPH", "TPX", "TR", "TREX", "TRMK", "TRN",
    "TRMR", "TSC", "TTEC", "TTGT", "TUP", "TWI", "TXRH", "TYL", "UCB",
    "UCTT", "UE", "UFI", "UGI", "UHT", "UIL", "UMBF", "UNF", "UNFI", "UNIT",
    "UVE", "UVV", "VAC", "VBTX", "VC", "VFC", "VGR", "VHI", "VICR", "VIR",
    "VLY", "VMI", "VNO", "VOYA", "VPG", "VRE", "VSCO", "VSH", "VVI", "VVV",
    "WABC", "WAL", "WASH", "WBS", "WD", "WDFC", "WEN", "WETF", "WEX", "WH",
    "WHD", "WHR", "WKC", "WLK", "WMS", "WOR", "WPM", "WRB", "WS", "WSO",
    "WTFC", "WTS", "WU", "WWE", "WY", "XPEL", "XRX", "XNCR", "YELP", "YOU",
    "ZWS",
]


def _load_metadata() -> dict:
    if METADATA_PATH.exists():
        age = time.time() - METADATA_PATH.stat().st_mtime
        if age < 86400:
            try:
                return json.loads(METADATA_PATH.read_text())
            except Exception:
                return {}
    return {}


def _load_or_build_ticker_list() -> list:
    sp400_sp600 = [
        "MMM","AOS","ABT","ABBV","ACN","ADBE","AMD","AES","AFL","A",
        "APD","ABNB","AKAM","ALB","ARE","ALGN","ALLE","LNT","ALL",
        "GOOGL","GOOG","MO","AMZN","AMCR","AEE","AAL","AEP","AXP",
        "AIG","AMT","AWK","AMP","AME","AMGN","APH","ADI","ANSS","AON",
        "APA","AAPL","AMAT","APTV","ACGL","ADM","ANET","AJG","AIZ",
        "T","ATO","ADSK","ADP","AZO","AVB","AVY","AXON","BKR","BALL",
        "BAC","BK","BBWI","BAX","BDX","WRB","BBY","BIO","TECH","BIIB",
        "BLK","BX","BA","BCF","BSX","BMY","AVGO","BR","BRO","BF-B",
        "BLDR","BG","CDNS","CZR","CPT","CPB","COF","CAH","KMX","CCL",
        "CARR","CTLT","CAT","CBOE","CBRE","CDW","CE","COR","CNC","CNX",
        "CHRW","CRL","SCHW","CHTR","CVX","CMG","CB","CHD","CI","CINF",
        "CTAS","CSCO","C","CFG","CLX","CME","CMS","KO","CTSH","CL",
        "CMCSA","CMA","CAG","COP","ED","STZ","CEG","COO","CPRT","GLW",
        "CTVA","CSGP","COST","CTRA","CCI","CSX","CMI","CVS","DHI",
        "DHR","DRI","DVA","DAY","DECK","DE","DAL","XRAY","DVN","DXCM",
        "FANG","DLR","DFS","DG","DLTR","D","DPZ","DOV","DOW","DHR",
        "DTE","DUK","DD","EMN","ETN","EBAY","ECL","EIX","EW","EA",
        "ELV","LLY","EMR","ENPH","ETR","EOG","EPAM","EQT","EFX","EQIX",
        "EQR","ESS","EL","ETSY","EG","EVRG","ES","EXC","EXPE","EXPD",
        "EXR","XOM","FFIV","FDS","FICO","FAST","FRT","FDX","FIS","FITB",
        "FSLR","FE","FI","FLT","FMC","F","FTNT","FTV","FOXA","FOX",
        "BEN","FCX","GRMN","IT","GE","GEHC","GEV","GEN","GNRC","GD",
        "GIS","GM","GPC","GILD","GPN","GL","GDDY","GS","HAL","HIG",
        "HAS","HCA","DOC","HSIC","HSY","HES","HPE","HLT","HOLX","HD",
        "HON","HRL","HST","HWM","HPQ","HUBB","HUM","HBAN","HII","IBM",
        "IEX","IDXX","ITW","INCY","IR","PODD","INTC","ICE","IFF","IP",
        "IPG","INTU","ISRG","IVZ","INVH","IQV","IRM","JBHT","JBL",
        "JKHY","J","JNJ","JCI","JPM","JNPR","K","KVUE","KDP","KEY",
        "KEYS","KMB","KIM","KMI","KLAC","KHC","KR","LHX","LH","LRCX",
        "LW","LVS","LDOS","LEN","LNC","LIN","LYV","LKQ","LMT","L",
        "LOW","LULU","LYB","MTB","MRO","MPC","MKTX","MAR","MMC","MLM",
        "MAS","MA","MTCH","MKC","MCD","MCK","MDT","MRK","META","MET",
        "MTD","MGM","MCHP","MU","MSFT","MAA","MRNA","MHK","MOH","TAP",
        "MDLZ","MPWR","MNST","MCO","MS","MOS","MSI","MSCI","NDAQ",
        "NTAP","NFLX","NEM","NWSA","NWS","NEE","NKE","NI","NDSN","NSC",
        "NTRS","NOC","NCLH","NRG","NUE","NVDA","NVR","NXPI","ORLY",
        "OXY","ODFL","OMC","ON","OKE","ORCL","OTIS","PCAR","PKG","PANW",
        "PH","PAYX","PAYC","PYPL","PNR","PEP","PFE","PCG","PM","PSX",
        "PNW","PXD","PNC","POOL","PPG","PPL","PFG","PG","PGR","PLD",
        "PRU","PEG","PTC","PSA","PHM","QRVO","PWR","QCOM","DGX","RL",
        "RJF","RTX","O","REG","REGN","RF","RSG","RMD","RVTY","ROK",
        "ROL","ROP","ROST","RCL","SPGI","CRM","SBAC","SLB","STX","SRE",
        "NOW","SHW","SPG","SWKS","SJM","SNA","SOLV","SO","LUV","SWK",
        "SBUX","STT","STLD","STE","SYK","SMCI","SYF","SNPS","SYY",
        "TMUS","TROW","TTWO","TPR","TRGP","TGT","TEL","TDY","TFX",
        "TER","TSLA","TXN","TXT","TMO","TJX","TSCO","TT","TDG","TRV",
        "TRMB","TFC","TYL","TSN","USB","UDR","ULTA","UNP","UAL","UPS",
        "URI","UNH","UHS","VLO","VTR","VLTO","VRSN","VRSK","VZ","VRTX",
        "VTRS","VICI","V","VST","VNO","VMC","WRK","WAB","WMT","WBD",
        "WM","WAT","WEC","WFC","WELL","WST","WDC","WY","WHR","WMB",
        "WTW","GWW","WYNN","XEL","XYL","YUM","ZBRA","ZBH","ZTS",
        # S&P 400 Mid-Cap
        "AAN","ACC","ACHC","ACIW","ACM","ADNT","AEO","AFG","AGCO",
        "AGL","AIRC","AIN","AIR","ALE","ALGM","ALKS","ALLE","ALV",
        "AMCX","AMG","AMKR","AMNB","AMR","AMRC","AMSF","AN","ANGI",
        "ANF","APA","APAM","APG","APOG","APPF","APRI","ARI","ARW",
        "ASB","ASH","ASGN","ASTE","ATI","ATNI","ATRC","AUB","AVA",
        "AVNT","AWI","AX","AXNX","AXS","AZPN","B","BCO","BECN","BFH",
        "BFIN","BGC","BHF","BJ","BLKB","BLD","BMI","BPOP","BRC","BRX",
        "BSIG","BURL","BWXT","BY","BYD","CABO","CADE","CAKE","CALM",
        "CARG","CBT","CCCS","CEIX","CHE","CHEF","CHRD","CIR","CKH",
        "CLAR","CLH","CLVT","CMCO","CMP","CNO","CNXN","CNX","COHU",
        "COLM","CONE","COOP","CORT","CPF","CPRX","CRC","CROX","CRS",
        "CRVL","CSL","CSWC","CTRE","CUZ","CW","DAN","DBD","DCI","DCO",
        "DCP","DFIN","DKS","DLB","DORM","DRH","DRQ","DY","EAT","EBTC",
        "EFC","EGP","EHC","ELAN","ELF","ENOV","ENS","ENSG","EPAC",
        "ESE","ESNT","ESSA","ESTC","EVI","EXP","EXPI","FAF","FBP",
        "FCEL","FCFS","FCF","FG","FHB","FHI","FLO","FLR","FLY","FNB",
        "FND","FNF","FOR","FORM","FOUR","FR","FUL","GEO","GKOS","GLT",
        "GLTR","GNRC","GNW","GPOR","GRC","GRX","GT","GTLS","GVA","H",
        "HAE","HAYW","HBI","HCAT","HCC","HCI","HCSG","HHH","HI","HIW",
        "HLF","HMN","HMST","HNST","HOG","HOMB","HOME","HPP","HR","HRI",
        "HUBG","HUN","IAA","IART","IBP","IDCC","IDEX","INN","INSM",
        "ITGR","JACK","JELD","JHG","JLL","JOBY","JWN","KBH","KFRC",
        "KFY","KNF","KNX","KRC","KRG","KSS","KTB","KTOS","LGF-A",
        "LGF-B","LHX","LKQ","LMAT","LNC","LNW","LOPE","LPX","LRN",
        "LSTR","LTC","LXP","M","MAC","MAN","MATW","MBC","MBWM","MC",
        "MCRI","MD","MDU","MHO","MMS","MMSI","MODG","MOR","MOV","MP",
        "MPLX","MRC","MRCY","MSEX","MTG","MTN","MTZ","MUR","NARI",
        "NBR","NEO","NEOG","NFG","NFBK","NJR","NNN","NOMD","NPO","NWE",
        "NWSA","OFG","OGE","OGS","OI","OII","OLN","OMCL","OMF","ONB",
        "ORA","OSK","OUT","OZK","PABI","PAG","PAHC","PATK","PAYO",
        "PBF","PBH","PBPB","PCH","PDCE","PEBO","PENN","PII","PINC",
        "PIPR","PJT","PLAY","PLXS","PNFP","PNM","POOL","POST","PPBI",
        "PRG","PRGO","PRGS","PRIM","PRK","PSMT","PTC","PTCT","PUMP",
        "PVH","R","RBC","REXR","RGLD","RHP","RIG","RLI","RNR","ROAD",
        "RXO","SBH","SBRA","SCSC","SEIC","SF","SFM","SG","SHAK","SHO",
        "SIG","SITC","SKT","SKX","SLG","SM","SMAR","SMG","SNDR","SNV",
        "SPSC","SPT","SRI","SS","SSYS","STAG","STRA","SUM","SWN","SWX",
        "SYNA","TALO","TBBK","TCF","TCBI","TDS","TFSL","THO","THR",
        "TKR","TMP","TNET","TNL","TOWN","TPH","TRMK","TRNO","TRN",
        "TROW","TRS","TSEM","TTC","TVTX","TWI","TXRH","UCBI","UFPI",
        "UGI","UMBF","UMPQ","UNFI","UNIT","URBN","USLM","USPH","UTL",
        "VCEL","VFC","VIPS","VLY","VMI","VNT","VOYA","VRE","VSCO",
        "WAFD","WAL","WASH","WD","WEN","WERN","WEX","WGO","WINA","WK",
        "WLK","WMS","WOLF","WOR","WPC","WS","WTFC","WWE","X","XHR",
        "XPEL","XPO","YELP","ZI","ZION"
    ]
    tickers = list(dict.fromkeys(sp400_sp600))
    print(f"[scanner] using {len(tickers)} hardcoded S&P 400+600 tickers")
    return tickers


ALL_TICKERS = _load_or_build_ticker_list()


def _fetch_and_save_metadata(tickers):
    result = {}
    batches = [tickers[i : i + 20] for i in range(0, len(tickers), 20)]
    for i, batch in enumerate(batches):
        for ticker in batch:
            try:
                t = yf.Ticker(ticker)
                info = t.info
                hist = t.history(period="3mo", interval="1d").dropna()
                last = float(hist["Close"].iloc[-1]) if len(hist) > 0 else None
                result[ticker] = {
                    "name": info.get("shortName") or info.get("longName") or ticker,
                    "market_cap": info.get("marketCap"),
                    "roe": (info.get("returnOnEquity") or 0) * 100,
                    "change_15d": (last / float(hist["Close"].iloc[-15]) - 1) * 100
                    if last and len(hist) >= 15
                    else None,
                    "change_1m": (last / float(hist["Close"].iloc[-21]) - 1) * 100
                    if last and len(hist) >= 21
                    else None,
                    "change_3m": (last / float(hist["Close"].iloc[-63]) - 1) * 100
                    if last and len(hist) >= 63
                    else None,
                }
                with _scanner_cache_lock:
                    data = {**result[ticker], "ticker": ticker}
                    existing = next(
                        (x for x in _scanner_cache
                         if x.get('ticker') == data.get('ticker')),
                        None
                    )
                    if existing:
                        existing.update(data)
                    else:
                        _scanner_cache.append(data)
            except Exception as e:
                print(f"[metadata] {ticker} failed: {e}")
        print(f"[metadata] batch {i + 1}/{len(batches)} done")
        time.sleep(2)
    try:
        _APP_DATA.mkdir(parents=True, exist_ok=True)
        METADATA_PATH.write_text(json.dumps(result))
        print("[metadata] saved to disk")
    except Exception as e:
        print(f"[metadata] save failed: {e}")


def _safe_float(value, default: float = 0.0) -> float:
    try:
        num = float(value)
        if pd.isna(num):
            return default
        return num
    except (TypeError, ValueError):
        return default


def _fetch_yfinance_extras(ticker: str) -> dict:
    """Fetch quote fields and sparkline from yfinance."""
    try:
        configure_yfinance_cache()
        import yfinance as yf

        stock = yf.Ticker(ticker)
        try:
            info = stock.info or {}
        except Exception:
            info = {}

        prev_close = _safe_float(
            info.get("previousClose") or info.get("regularMarketPreviousClose")
        )
        price = _safe_float(
            info.get("currentPrice")
            or info.get("regularMarketPrice")
            or info.get("previousClose")
        )
        change = price - prev_close if prev_close else 0.0
        change_pct = (change / prev_close * 100) if prev_close else 0.0

        sparkline: list[float] = []
        hist = safe_ticker_history(ticker, period="5d", interval="1h")
        if hist is not None and not hist.empty:
            close_col = "Close" if "Close" in hist.columns else "close"
            closes = hist[close_col].dropna().tail(10)
            sparkline = [round(_safe_float(v), 4) for v in closes.tolist()]

        hist_daily = safe_ticker_history(ticker, period="3mo", interval="1d")

        if hist_daily is not None and not hist_daily.empty:
            closes = hist_daily["Close"].dropna()
            current = closes.iloc[-1] if len(closes) > 0 else None

            def pct_change_ago(days):
                if current is None or len(closes) < days:
                    return None
                past = closes.iloc[-days]
                return round((current - past) / past * 100, 2)

            change_3d = pct_change_ago(3)
            change_1w = pct_change_ago(5)   # 5 trading days
            change_15d = pct_change_ago(10)  # 10 trading days
            change_1m = pct_change_ago(21)  # 21 trading days
            change_3m = pct_change_ago(60)  # 60 trading days
        else:
            change_3d = change_1w = change_15d = change_1m = change_3m = None

        volume = _safe_float(info.get("volume") or info.get("regularMarketVolume"))
        market_cap = _safe_float(info.get("marketCap"))

        return {
            "price": round(price, 4),
            "change": round(change, 4),
            "change_pct": round(change_pct, 2),
            "prev_close": round(prev_close, 4),
            "open": round(_safe_float(info.get("open") or info.get("regularMarketOpen")), 4),
            "high": round(
                _safe_float(info.get("dayHigh") or info.get("regularMarketDayHigh")), 4
            ),
            "low": round(
                _safe_float(info.get("dayLow") or info.get("regularMarketDayLow")), 4
            ),
            "volume": int(volume) if volume else 0,
            "market_cap": int(market_cap) if market_cap else 0,
            "roe": round(_safe_float(info.get("returnOnEquity")) * 100, 2)
            if info.get("returnOnEquity")
            else None,
            "sparkline": sparkline,
            "change_3d": change_3d,
            "change_1w": change_1w,
            "change_15d": change_15d,
            "change_1m": change_1m,
            "change_3m": change_3m,
            "name": info.get("longName") or info.get("shortName") or ticker,
        }
    except Exception as e:
        print(f"[scanner] extras failed for {ticker}: {e}")
        return {
            "name": ticker,
            "price": None,
            "change": None,
            "change_pct": None,
            "prev_close": None,
            "open": None,
            "high": None,
            "low": None,
            "volume": None,
            "market_cap": None,
            "roe": None,
            "sparkline": [],
            "change_3d": None,
            "change_1w": None,
            "change_15d": None,
            "change_1m": None,
            "change_3m": None,
        }


def _bulk_fetch_signals(tickers: list[str]) -> dict:
    """Fetch 1-min bars for all tickers in one call,
    run ML on each slice. Returns dict of
    ticker -> signal data."""
    from feature_engineer import compute_indicators
    from ml_model import predict_signal

    results = {}

    try:
        ticker_str = " ".join(tickers)
        print(f"[scanner] bulk fetching {len(tickers)} tickers...")

        import time
        start = time.time()
        data = yf.download(
            ticker_str,
            period="5d",
            interval="1m",
            group_by="ticker",
            progress=False,
            threads=True,
        )
        elapsed = time.time() - start
        print(f"[scanner] bulk fetch done in {elapsed:.1f}s")

        if data is None or data.empty:
            return {}

        # Handle single ticker case
        if len(tickers) == 1:
            df = data.copy()
            df.columns = [
                (c[1].lower() if len(c) > 1 else c[0].lower())
                if isinstance(c, tuple) else c.lower()
                for c in df.columns
            ]
            df = df.dropna()
            if not df.empty:
                try:
                    df = compute_indicators(df)
                    latest = df.iloc[-1]
                    price = float(latest["close"])
                    features = _extract_features_from_row(latest, price)
                    from feature_engineer import features_to_ml_array
                    ml_result = predict_signal(features_to_ml_array(features))
                    signal = ml_result["signal"]
                    confidence = ml_result["confidence"]
                    if signal in ("BUY", "SELL") and confidence < 65:
                        signal = "HOLD"
                    results[tickers[0]] = {
                        "signal": signal,
                        "confidence": confidence,
                        "price": price,
                        "df": df,
                    }
                except Exception as e:
                    print(f"[scanner] signal failed for {tickers[0]}: {e}")
            return results

        # Multi-ticker case
        from feature_engineer import features_to_ml_array
        from concurrent.futures import ThreadPoolExecutor as _TPE

        available = data.columns.get_level_values(0).unique().tolist()

        # Pre-load ML model before threading to avoid race condition
        try:
            predict_signal(features_to_ml_array(
                _extract_features_from_row(
                    __import__('pandas').Series({
                        'close': 100.0, 'rsi': 50.0, 'macd': 0.0,
                        'macd_signal': 0.0, 'macd_hist': 0.0,
                        'ema_5': 100.0, 'ema_10': 100.0, 'ema_20': 100.0,
                        'atr': 1.0, 'vol_ratio': 1.0, 'volume': 1000.0,
                        'bb_upper': 105.0, 'bb_lower': 95.0,
                        'bb_position': 0.5, 'bb_score': 0.5,
                        'roc_5': 0.0, 'roc_20': 0.0,
                    }), 100.0)
            ))
        except Exception:
            pass

        def _process(ticker):
            if ticker not in available:
                return None
            try:
                df = data[ticker].copy()
                df.columns = [
                c[0].lower() if isinstance(c, tuple) else c.lower()
                for c in df.columns
            ]
                df = df.dropna()
                if df.empty or len(df) < 10:
                    return None
                df = compute_indicators(df)
                latest = df.iloc[-1]
                price = float(latest["close"])
                features = _extract_features_from_row(latest, price)
                ml_result = predict_signal(features_to_ml_array(features))
                raw_signal = ml_result["signal"]
                raw_confidence = ml_result["confidence"]
                if raw_signal in ("BUY", "SELL") and raw_confidence < 65:
                    raw_signal = "HOLD"
                return ticker, {
                    "signal": raw_signal,
                    "confidence": raw_confidence,
                    "price": price,
                    "df": df
                }
            except Exception as e:
                print(f"[scanner] signal failed for {ticker}: {e}")
                return None

        with _TPE(max_workers=8) as ex:
            for outcome in ex.map(_process, tickers):
                if outcome:
                    ticker, payload = outcome
                    results[ticker] = payload

    except Exception as e:
        print(f"[scanner] bulk fetch failed: {e}")

    return results


def _extract_features_from_row(latest, price: float) -> dict:
    """Extract ML feature dict from a computed indicators row."""
    from feature_engineer import classify_volume
    import math

    def safe(key, default=0.0):
        try:
            val = latest.get(key, default)
            if val is None:
                return default
            f = float(val)
            return default if math.isnan(f) or math.isinf(f) else f
        except:
            return default

    vol_ratio = safe("vol_ratio", 1.0)
    rsi = safe("rsi", 50.0)
    macd = safe("macd", 0.0)
    macd_signal = safe("macd_signal", 0.0)
    ma5 = safe("ema_5", price)
    ma10 = safe("ema_10", price)
    ma20 = safe("ema_20", price)

    # ma_signal
    if price > ma5 and price > ma10 and price > ma20:
        ma_signal = "bullish"
    elif price < ma5 and price < ma10 and price < ma20:
        ma_signal = "bearish"
    else:
        ma_signal = "neutral"

    # long_trend
    if ma5 > ma20:
        long_trend = "uptrend"
    else:
        long_trend = "downtrend"

    # macd_for_ml
    if macd > macd_signal:
        macd_for_ml = "bullish"
    elif macd < macd_signal:
        macd_for_ml = "bearish"
    else:
        macd_for_ml = "neutral"

    # rsi_for_ml
    if rsi >= 70:
        rsi_for_ml = 1.0
    elif rsi <= 30:
        rsi_for_ml = 0.0
    else:
        rsi_for_ml = (rsi - 30) / 40

    # roc_5 and roc_20 from close history
    roc_5 = safe("roc_5", 0.0)
    roc_20 = safe("roc_20", 0.0)

    return {
        "price": price,
        "ma5": ma5,
        "ma10": ma10,
        "ma20": ma20,
        "rsi": rsi,
        "rsi_for_ml": rsi_for_ml,
        "macd": macd,
        "macd_signal": macd_signal,
        "macd_hist": safe("macd_hist", 0.0),
        "macd_for_ml": macd_for_ml,
        "atr": safe("atr", 0.0),
        "bb_upper": safe("bb_upper", price),
        "bb_lower": safe("bb_lower", price),
        "bb_position": safe("bb_position", 0.5),
        "bb_score": safe("bb_score", 0.5),
        "volume": safe("volume", 0.0),
        "vol_ratio": vol_ratio,
        "volume_label": classify_volume(vol_ratio),
        "ma_signal": ma_signal,
        "long_trend": long_trend,
        "roc_5": roc_5,
        "roc_20": roc_20,
        "vwap": safe("vwap", price),
        "adx": safe("adx", 20.0),
        "adx_signal": "bullish" if safe("adx", 20.0) > 25 else "neutral",
        "trend_strength": "strong" if safe("adx", 20.0) > 25 else "weak",
        "cci": safe("cci", 0.0),
        "resistance": safe("resistance", price * 1.05),
        "support": safe("support", price * 0.95),
        "change_pct": safe("change_pct", 0.0),
        "pivot_score": safe("pivot_score", 0.5),
    }


def _quick_signal(ticker: str) -> dict:
    """Get real ML signal for a single ticker using analyze_live()."""
    try:
        from signal_engine import analyze_live
        result = analyze_live(ticker)
        if not result:
            extras = _fetch_yfinance_extras(ticker)
            return {
                "ticker": ticker,
                "signal": "HOLD",
                "signal_color": "neutral",
                "confidence": 0,
                "rsi": 50,
                "vol_ratio": 1,
                "ma_trend": "bearish",
                "conclusion": "",
                **extras,
            }

        price = _safe_float(result.get("price"), 0)
        change_pct = _safe_float(result.get("change_pct"), 0)
        signal = result.get("signal", "HOLD")
        confidence = _safe_float(result.get("confidence"), 0)
        indicators = result.get("indicators", {})
        rsi = _safe_float(indicators.get("RSI"), 50)
        vol_ratio = _safe_float(indicators.get("vol_ratio"), 1)
        ma_trend = str(indicators.get("MA_trend", "") or "")
        ma5 = _safe_float(indicators.get("MA5"), None)
        ma10 = _safe_float(indicators.get("MA10"), None)
        ma20 = _safe_float(indicators.get("MA20"), None)
        ma_bias = (
            "bullish" if "bullish" in ma_trend.lower() or "above" in ma_trend.lower()
            else "bearish"
        )

        signal_color = (
            "bullish" if signal == "BUY"
            else "bearish" if signal == "SELL"
            else "neutral"
        )

        extras = _fetch_yfinance_extras(ticker)
        if not extras.get("price") and price:
            extras["price"] = round(price, 4)
            extras["change_pct"] = round(change_pct, 2)
            if extras.get("prev_close"):
                extras["change"] = round(extras["price"] - extras["prev_close"], 4)

        if not extras.get("price"):
            return {
                "ticker": ticker,
                "signal": signal,
                "signal_color": signal_color,
                "confidence": round(confidence, 1),
                "rsi": round(rsi, 1),
                "vol_ratio": round(vol_ratio, 2),
                "ma_trend": ma_bias,
                "ma5": ma5,
                "ma10": ma10,
                "ma20": ma20,
                "conclusion": result.get("conclusion", ""),
                **extras,
            }

        return {
            "ticker": ticker,
            "signal": signal,
            "signal_color": signal_color,
            "confidence": round(confidence, 1),
            "rsi": round(rsi, 1),
            "vol_ratio": round(vol_ratio, 2),
            "ma_trend": ma_bias,
            "ma5": ma5,
            "ma10": ma10,
            "ma20": ma20,
            "conclusion": result.get("conclusion", ""),
            **extras,
        }
    except Exception as e:
        print(f"[scanner] signal failed for {ticker}: {e}")
        return {
            "ticker": ticker,
            "signal": "HOLD",
            "confidence": 0,
            "name": ticker,
        }


def _run_background_scan():
    while True:
        try:
            print(f"[scanner] background scan starting — "
                  f"{len(ALL_TICKERS)} tickers...")
            start = _time.time()
            batches = [ALL_TICKERS[i:i+25]
                      for i in range(0, len(ALL_TICKERS), 25)]

            for i, batch in enumerate(batches):
                with ThreadPoolExecutor(max_workers=4) as executor:
                    futures = {
                        executor.submit(_quick_signal, ticker): ticker
                        for ticker in batch
                    }
                    for future in as_completed(futures):
                        ticker = futures[future]
                        try:
                            data = future.result(timeout=45)
                        except Exception as e:
                            print(f"[scanner] {ticker} failed: {e}")
                            data = None
                        if data:
                            signal = data.get("signal", "HOLD")
                            confidence = data.get("confidence", 0)
                            if signal in ("BUY", "SELL") and confidence < 65:
                                data["signal"] = "HOLD"
                            if data and data.get("price") is not None:
                                with _scanner_cache_lock:
                                    existing = next(
                                        (x for x in _scanner_cache
                                         if x.get('ticker') == data.get('ticker')),
                                        None
                                    )
                                    if existing:
                                        existing.update(data)
                                    else:
                                        _scanner_cache.append(data)
                            elif data and data.get("price") is None:
                                print(f"[scanner] {data.get('ticker')} skipped — no price data")

                # Set ready after first batch so UI loads fast
                if i == 0:
                    with _scanner_cache_lock:
                        cached_count = len(_scanner_cache)
                    _scanner_cache_ready.set()
                    print(f"[scanner] first batch ready — "
                          f"{cached_count} tickers cached")

                with _scanner_cache_lock:
                    cached_count = len(_scanner_cache)
                print(f"[scanner] batch {i+1}/{len(batches)} done, "
                      f"{cached_count} tickers so far")

                # Pause between batches to avoid rate limiting
                if i < len(batches) - 1:
                    _time.sleep(8)

            # Apply metadata from disk cache
            cached_meta = _load_metadata()
            if cached_meta:
                with _scanner_cache_lock:
                    for item in _scanner_cache:
                        t = item.get("ticker")
                        if t and t in cached_meta:
                            item.update({
                                k: cached_meta[t][k]
                                for k in ["name", "market_cap",
                                         "roe", "change_15d",
                                         "change_1m", "change_3m"]
                                if k in cached_meta[t]
                            })
                print("[metadata] applied from disk cache")
            else:
                threading.Thread(
                    target=_fetch_and_save_metadata,
                    args=(list(ALL_TICKERS),),
                    daemon=True,
                ).start()
                print("[metadata] fetching in background...")

            global _scan_complete
            _scan_complete = True
            print("[scanner] scan marked complete")

            with _scanner_cache_lock:
                cached_count = len(_scanner_cache)
            elapsed = _time.time() - start
            print(f"[scanner] scan complete in {elapsed:.1f}s — "
                  f"{cached_count} tickers cached")

        except Exception as e:
            print(f"[scanner] scan error: {e}")

        _time.sleep(900)


# Start background scan on import
_bg_thread = threading.Thread(target=_run_background_scan, daemon=True)
_bg_thread.start()


def _sort_change_pct(stock: dict, *, reverse: bool = True) -> tuple:
    pct = stock.get("change_pct")
    if pct is None:
        return (1, 0)
    return (0, -pct if reverse else pct)


def _sort_vol_ratio(stock: dict) -> tuple:
    vol = stock.get("vol_ratio")
    if vol is None:
        return (1, 0)
    return (0, -vol)


def get_scanner_list(category: str = "all") -> list[dict]:
    """Serve from cache instantly. Cache built by background thread."""
    # Wait for first scan to complete (only blocks on very first call)
    if not _scanner_cache_ready.is_set():
        print("[scanner] waiting for background scan to complete...")
        _scanner_cache_ready.wait()
    
    with _scanner_cache_lock:
        stocks = list(_scanner_cache)
    
    return stocks
