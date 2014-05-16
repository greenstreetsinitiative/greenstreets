# Create your views here.
from survey.models import Commutersurvey, Employer, EmplSector, Leg, Month
from django.shortcuts import render, get_object_or_404
from django.http import HttpResponse
from operator import itemgetter, attrgetter
import json
from django.shortcuts import redirect
from django.db import connections
from datetime import date

COLOR_SCHEME = {
        'gs': '#0096FF',
        'gc': '#65AB4B',
        'cc': '#FF2600',
        'us': '#9437FF',
        'hs': '#000000',
        'hc': '#f0f0f0',
        'rgs': '#0096FF',
        'rgc': '#65AB4B',
        'rcc': '#FF2600',
        'rus': '#9437FF',
        'ngs': '#00C8FF',
        'ngc': '#75FF57',
        'ncc': '#FF266E',
        'nus': '#9496FF',
        }

def index(request):
    latest_check_ins = Commutersurvey.objects.order_by('month')[:5]
    reply_data = leaderboard_reply_data('perc', month, 'sector', '2');
    context = {'latest_check_ins' : latest_check_ins, 'reply_data' : reply_data }
    return render(request, 'leaderboard/index.html', context)

def lb_redirect(request):
    if request.GET['color'] == "sector":
        val = request.GET['sector_filter']
    elif request.GET['color'] == "size":
        val = request.GET['size_filter']
    elif request.GET['color'] == "nofilter":
        return redirect("/leaderboard/", permanent=True)
    url = "/leaderboard/"
    if 'empid' in request.GET:
        url += request.GET['empid']+'/'
    url += request.GET['color']+"/"+val+"/"
    if 'sort' in request.GET:
        url += request.GET['sort']+'/'
    if 'month' in request.GET:
        url += 'month_'
        url += request.GET['month']
    return redirect(url, permanent=True)

nmonths = 1

def new_leaderboard(request, empid=0, filter_by='sector', _filter=0, sort='participation', selmonth='all'):

    db = connections['default'].cursor()
    context = {}
    context['empid'] = empid
    global nmonths
    surveys_cache = {} 
    breakdown = {}
 
    if _filter == '0':
        _filter = 0
   
    if empid != 0:
        res = Employer.objects.filter(id=empid)
        emp = res[0]
        sector = emp.sector
    if empid != 0 and _filter == 0:
        _filter = sector.id

    context['filter_by'] = filter_by
    context['filt'] = _filter
    if filter_by == 'sector':
        context['sectorid'] = _filter
    context['sort'] = sort
    context['sectors'] = sorted(EmplSector.objects.all(), key=getSectorNum)
    context['subteams'] = get_subteams()
    months = Month.objects.active_months().reverse().exclude(open_checkin__gt=date.today() )
    context['months'] = months
    for m in months:
        if m.url_month == selmonth:
            month = m.id
            old_month = m.month
            context['display_month'] = m.month

    if selmonth == 'all':
        month = 'all'
        old_month = 'all'
        context['display_month'] = "all months"
        nmonths = len(months)
    else:
        nmonths = 1

    if filter_by == 'size':
        if _filter == 0:
            context['sizecat'] = 'all sizes';
        if _filter == '1':
            context['sizecat'] = 'small companies';
        if _filter == '2':
            context['sizecat'] = 'medium companies';
        if _filter == '3':
            context['sizecat'] = 'large companies';
        if _filter == '4':
            context['sizecat'] = 'largest companies';


    context['current_month'] = selmonth

    context['ranks'] = participation_rankings(month, filter_by, _filter)
    context['ranks_pct'] = participation_pct(month, filter_by, _filter)
    
    context['total_companies'] = len(context['ranks_pct'])
    context['total'] = 0
    for rank in context['ranks']:
        context['total'] += rank[0]
    
    if _filter == 0:
        context['emp_sector'] = 'all sectors'
    elif filter_by == 'sector' and empid == 0:
        sector = EmplSector.objects.filter(id=_filter)
        context['emp_sector'] = sector[0]
    if empid != 0:
        context['chart'] = json.dumps(getCanvasJSChart(emp) )
        stats_month = getBreakDown(emp, month)
        stats_all = stats_month
        if month != 'all':
            stats_all = getBreakDown(emp, 'all')
        for count in context['ranks']:
            if count[2] == int(empid):
                nsurveys = count[0]
        for count in context['ranks_pct']:
            if count[2] == int(empid):
                context['participation'] = count[0]

        context['ncommutes'] = nsurveys*2
        context['gc'] = stats_month['gc']
        context['gs'] = stats_month['gs']

        context['gs_total'] = stats_all['gs']
        context['gc_total'] = stats_all['gc']
        context['cc_total'] = stats_all['cc']
        context['other_total'] = stats_all['us']
        context['ncommutes_total'] = stats_all['total']

        if nsurveys != 0:
            context['gc_pct'] = ( ( stats_month['gc']*1.0) / (nsurveys*2.0) ) * 100
            context['gs_pct'] = ( ( stats_month['gs']*1.0) / (nsurveys*2.0) ) * 100
        else:
            context['gs_pct'] = 0
            context['gc_pct'] = 0
        context['stats'] = stats_month
        context['employer'] = emp
        context['emp_sector'] = emp.sector
        context['sectorid'] = emp.sector.id
        
    return render(request, 'leaderboard/leaderboard_js.html', context)

def getSectorNum(sector):
        return sector.id


def get_subteams():
    sectors = sorted(EmplSector.objects.all(), key=getSectorNum)
    subteams = []
    for sector in sectors:
        if sector.id > 9:
            subteams.append(sector)

    return subteams

def getEmpCheckinMatrix(emp, month):

    checkinMatrix = {}
    modes = [ 'c', 'cp', 'da', 'dalt', 'w', 'b', 'r', 't', 'o', 'tc' ]
    for mode in modes:
        checkinMatrix[mode] = {}
        for mode2 in modes:
            checkinMatrix[mode][mode2] = 0

    empCommutes = get_lb_surveys(emp, month)
    for emp in empCommutes:
        if from_work_normally(emp) and from_work_today(emp) and to_work_normally(emp) and to_work_today(emp):
            checkinMatrix[from_work_today(emp)][from_work_normally(emp)] += 1
            checkinMatrix[to_work_today(emp)][to_work_normally(emp)] += 1
    return checkinMatrix

def participation_rankings(month, filter_by, _filter=0):
    db = connections['default'].cursor()
    args = []
    
    if month != 'all':
        monthq = "wr_day_month_id = %s";
        montharg = month
        args.append(montharg)
    else:
        monthq = " wr_day_month_id in (select id from survey_month where active = %s) "
        montharg = 't';
        args.append(montharg)
    if filter_by == 'size' and _filter != 0:
        filterq = " and e.size_cat_id = %s "
        subteam_filterq = " and e2.size_cat_id = %s "
        args.append(_filter)
    elif filter_by == 'sector' and _filter != 0:
        filterq = " and e.sector_id = %s "
        subteam_filterq = " and e2.sector_id = %s "
        args.append(_filter)
    else:
        filterq = ""
        subteam_filterq = ""

    if filter_by == 'sector' and _filter > 9:
        sectorq = ""
    else:
        sectorq = " and sector_id < 10 "

    if len(monthq) > 1:
        args.append(montharg)
    if len(filterq) > 1:
        args.append(_filter)

    db.execute("select count(cs.id) as nsurveys, e.name, e.id from survey_commutersurvey as cs join survey_employer as e on (employer_id = e.id) where " + monthq + sectorq + filterq + " and e.is_parent = 'f' and e.nr_employees > 0 group by e.name, e.id " +
    "union all select count(cs.id) as nsurveys, sec.parent, e2.id from survey_commutersurvey cs join survey_employer e on (cs.employer_id = e.id) join survey_emplsector sec on (e.sector_id = sec.id), survey_employer e2 where sec.parent is not null and e2.name = sec.parent and " + monthq + subteam_filterq + " group by sec.parent, e2.id order by nsurveys desc", args)
    return db.fetchall()


def participation_pct(month, filter_by, _filter=0):
    db = connections['default'].cursor() 
    args = []
    
    if month != 'all':
        monthq = "wr_day_month_id = %s";
        montharg = month
        args.append(montharg)
        pctq = "1"
    else:
        monthq = " wr_day_month_id in (select id from survey_month where active = %s) "
        montharg = 't';
        args.append(montharg)
        pctq="(select count(*) from survey_month where open_checkin < current_date and active = 't')"
    if filter_by == 'size' and _filter != 0:
        filterq = " and e.size_cat_id = %s "
        subteam_filterq = " and e2.size_cat_id = %s "
        args.append(_filter)
    elif filter_by == 'sector' and _filter != 0:
        filterq = " and e.sector_id = %s "
        subteam_filterq = " and e2.sector_id = %s "
        args.append(_filter)
    else:
        filterq = ""

    if filter_by == 'sector' and _filter > 9:
        sectorq = ""
    else:
        sectorq = " and sector_id < 10 "

    if len(monthq) > 1:
        args.append(montharg)
    if len(filterq) > 1:
        args.append(_filter)

    db.execute("select count(cast(cs.id as float8) ) / (cast(e.nr_employees*"+pctq+" as float8) ) * 100 as pct, e.name, e.id from survey_commutersurvey as cs join survey_employer as e on (employer_id = e.id) where " + monthq + sectorq + filterq + " and e.is_parent = 'f' and e.nr_employees > 0 group by e.name, e.id " + 
    "union all select count(cast(cs.id as float8) ) / (cast(e2.nr_employees*"+pctq+" as float8) ) * 100 as pct, sec.parent, e2.id from survey_commutersurvey cs join survey_employer e on (cs.employer_id = e.id) join survey_emplsector sec on (e.sector_id = sec.id), survey_employer e2 where sec.parent is not null and e2.name = sec.parent and e2.nr_employees > 0 and " + monthq + subteam_filterq + " group by sec.parent, e2.id, e2.nr_employees order by pct desc", args)
    return db.fetchall()


def getBreakDown(emp, month):
    hs = 0
    hc = 0
    gs = 0
    gc = 0
    cc = 0
    other = 0

    highest_fw_n = 0
    highest_fw_w = 0
    highest_tw_n = 0
    highest_tw_w = 0

    tw_w_mode = ''
    tw_n_mode = ''
    fw_w_mode = ''
    fw_n_mode = ''

    db = connections['default'].cursor()
    args = []
    if emp.is_parent == True:
        eid = " employer_id in (select id from survey_employer where sector_id in (select id from survey_emplsector where parent = %s) ) "
        args.append(emp.name)
    else:
        eid = " employer_id = %s "
        args.append(emp.id)

    if month == 'all':
        monthq = " wr_day_month_id in (select id from survey_month where active = %s) "
        args.append('t')
    else:
        monthq = " wr_day_month_id = %s "
        args.append(month)

    db.execute("select commutersurvey_id, direction, day,  mode, case when mode in ('b', 'r', 'w', 'o') then 5 when mode = 'tc' then 4 when mode = 't' then 3 when mode = 'cp' then 2 when mode in ('c', 'da') then 1 end as rank, wr_day_month_id from survey_leg join survey_commutersurvey cs on (commutersurvey_id = cs.id) where " + eid + " and " + monthq + " order by commutersurvey_id", args);
    surveys = db.fetchall()

    breakdown = {}
    modes = [ 'c', 'cp', 'da', 'dalt', 'w', 'b', 'r', 't', 'o', 'tc' ]
    for mode in modes:
        breakdown[mode] = {}
        for mode2 in modes:
            breakdown[mode][mode2] = 0
    breakdown['total'] = 0

    i = 1
    if len(surveys) != 0:
        lastid = surveys[0][0]
        for survey in surveys:
            if survey[0] != lastid or i == len(surveys):
                breakdown['total'] += 2
                if highest_fw_w > highest_fw_n and highest_fw_w == 5:
                    gs += 1 # formerly healthy switch, now green
                elif highest_fw_w == 5:
                    gc += 1 # formerly healthy commute, now green
                elif highest_fw_w > highest_fw_n:
                    gs += 1 # green switch
                elif highest_fw_w > 1:
                    gc += 1 # green commute
                elif highest_fw_w < highest_fw_n:
                    other += 1 # other (less healthy/green switch)
                elif highest_fw_w == 1:
                    cc += 1 # car commute
                
                if highest_tw_w > highest_tw_n and highest_tw_w == 5:
                    gs += 1 # former healthy switch
                elif highest_tw_w == 5:
                    gc += 1 # former healthy commute
                elif highest_tw_w > highest_tw_n:
                    gs += 1 # green switch
                elif highest_tw_w > 1:
                    gc += 1 # green commute
                elif highest_tw_w < highest_tw_n:
                    other += 1 # other (less healthy/green switch)
                elif highest_tw_w == 1:
                    cc += 1 # car commute

                if tw_w_mode and tw_n_mode and fw_w_mode and fw_n_mode:
                    breakdown[fw_w_mode][fw_n_mode] += 1
                    breakdown[tw_w_mode][tw_n_mode] += 1

                highest_fw_w = 0
                highest_tw_w = 0
                highest_fw_n = 0
                highest_tw_n = 0

            if survey[1] == 'fw' and survey[2] == 'n' and survey[4] > highest_fw_n:
                highest_fw_n = survey[4]
                fw_n_mode = survey[3]
            elif survey[1] == 'tw' and survey[2] == 'n' and survey[4] > highest_tw_n:
                highest_tw_n = survey[4]
                tw_n_mode = survey[3]
            elif survey[1] == 'fw' and survey[2] == 'w' and survey[4] > highest_fw_w:
                highest_fw_w = survey[4]
                fw_w_mode = survey[3]
            elif survey[1] == 'tw' and survey[2] == 'w' and survey[4] > highest_tw_w:
                highest_tw_w = survey[4]
                tw_w_mode = survey[3]


            lastid = survey[0]
            i += 1

    breakdown['gs'] = gs
    breakdown['gc'] = gc
    breakdown['us'] = other
    breakdown['cc'] = cc

    return breakdown


def getNewVOldBD(emp, month):
    nvoBD = {'nus':0, 'ncc':0, 'ngc':0, 'ngs':0, 'rus':0, 'rcc':0, 'rgc':0, 'rgs':0, 'ntotal':0, 'rtotal':0} # new vs. old breakdown
    for survey in emp.get_new_surveys(month):
        tws = survey.to_work_switch
        fws = survey.from_work_switch
        if tws == 1: nvoBD['nus'] += 1
        elif tws == 2: nvoBD['ncc'] += 1
        elif tws == 3: nvoBD['ngc'] += 1
        elif tws == 4: nvoBD['ngs'] += 1
        elif fws == 2: nvoBD['ncc'] += 1
        elif fws == 3: nvoBD['ngc'] += 1
        elif fws == 4: nvoBD['ngs'] += 1
    for survey in emp.get_returning_surveys(month):
        tws = survey.to_work_switch
        fws = survey.from_work_switch
        if tws == 1: nvoBD['rus'] += 1
        elif tws == 2: nvoBD['rcc'] += 1
        elif tws == 3: nvoBD['rgc'] += 1
        elif tws == 4: nvoBD['rgs'] += 1
        if fws == 1: nvoBD['rus'] += 1
        elif fws == 2: nvoBD['rcc'] += 1
        elif fws == 3: nvoBD['rgc'] += 1
        elif fws == 4: nvoBD['rgs'] += 1
    nvoBD['ntotal'] = nvoBD['nus'] + nvoBD['ncc'] + nvoBD['ngc'] + nvoBD['ngs']
    nvoBD['rtotal'] = nvoBD['rus'] + nvoBD['rcc'] + nvoBD['rgc'] + nvoBD['rgs']
    return nvoBD

def getCanvasJSChart(emp, new=False):
    if new:
        chartData = getNvRcJSChartData(emp)
    else:
        chartData = getCanvasJSChartData(emp)
    barChart = {
            'title': {
                'text': "Walk Ride Day Participation Over Time",
                'fontSize': 20 },
            'data': chartData
            }
    if new:
        barChart['title']['text'] = "New And Returning Walk Ride Day Participation Over Time"
    return barChart

def getCanvasJSChartData(emp):
    chartData = [
            {
                'type': "stackedColumn",
                'color': COLOR_SCHEME['gs'],
                'legendText': "Green Switches",
                'showInLegend': "true",
                'toolTipContent': '{name}: {y}',
                'dataPoints': [
                    ]
                },
            {
                'type': "stackedColumn",
                'color': COLOR_SCHEME['gc'],
                'legendText': "Green Commutes",
                'showInLegend': "true",
                'toolTipContent': '{name}: {y}',
                'dataPoints': [
                    ]
                },
            {
                'type': "stackedColumn",
                'color': COLOR_SCHEME['cc'],
                'legendText': "Car Commutes",
                'showInLegend': "true",
                'toolTipContent': '{name}: {y}',
                'dataPoints': [
                    ]
                },
            {
                'type': "stackedColumn",
                'color': COLOR_SCHEME['us'],
                'legendText': "Other",
                'showInLegend': "true",
                'toolTipContent': '{name}: {y}',
                'dataPoints': [
                    ]
                }
            
            ]
    intToModeConversion = ['gs', 'gc', 'cc', 'us' ]
    iTMSConv = ['Green Switches','Green Commutes', 'Car Commutes', 'Other', 'Healthy Switch', 'Healthy Commute']
    for m in Month.objects.active_months().reverse():
        breakDown = getBreakDown(emp, m.id)
        for i in range(0, 4):
            chartData[i]['dataPoints'] += [{ 'label': m.short_name, 'y': breakDown[intToModeConversion[i]], 'name': iTMSConv[i] },]
    return chartData

def getNvRcJSChartData(emp):
    chartData = [
            {
                'type': "stackedColumn",
                'color': COLOR_SCHEME['ngs'],
                'legendText': 'New Green Switches',
                'showInLegend': 'true',
                'toolTipContent': '{name}: {y}',
                'dataPoints': [
                    ],
                },
            {
                'type': "stackedColumn",
                'color': COLOR_SCHEME['rgs'],
                'legendText': 'Returning Green Switches',
                'showInLegend': 'true',
                'toolTipContent': '{name}: {y}',
                'dataPoints': [
                    ],
                },
            {
                'type': "stackedColumn",
                'color': COLOR_SCHEME['ngc'],
                'legendText': 'New Green Commutes',
                'showInLegend': 'true',
                'toolTipContent': '{name}: {y}',
                'dataPoints': [
                    ],
                },
            {
                'type': "stackedColumn",
                'color': COLOR_SCHEME['rgc'],
                'legendText': 'Returning Green Commutes',
                'showInLegend': 'true',
                'toolTipContent': '{name}: {y}',
                'dataPoints': [
                    ],
                },
            {
                'type': "stackedColumn",
                'color': COLOR_SCHEME['ncc'],
                'legendText': 'New Car Commutes',
                'showInLegend': 'true',
                'toolTipContent': '{name}: {y}',
                'dataPoints': [
                    ],
                },
            {
                'type': "stackedColumn",
                'color': COLOR_SCHEME['rcc'],
                'legendText': 'Returning Car Commutes',
                'showInLegend': 'true',
                'toolTipContent': '{name}: {y}',
                'dataPoints': [
                    ],
                },
            {
                'type': "stackedColumn",
                'color': COLOR_SCHEME['nus'],
                'legendText': 'New Other Commutes',
                'showInLegend': 'true',
                'toolTipContent': '{name}: {y}',
                'dataPoints': [
                    ],
                },
            {
                'type': "stackedColumn",
                'color': COLOR_SCHEME['rus'],
                'legendText': 'Returning Other Commutes',
                'showInLegend': 'true',
                'toolTipContent': '{name}: {y}',
                'dataPoints': [
                    ],
                },
            ]
    intToModeConversion = ['ngs', 'rgs', 'ngc', 'rgc', 'ncc', 'rcc', 'nus', 'rus']
    iTMSConv = ['New Green Switches', 'Returning Green Switches', 'New Green Commutes', 'Returning Green Commutes', 'New Car Commutes', 'Returning Car Commutes', 'New Other', 'Returning Other']
    for month in reversed(Month.objects.active_months_list()):
        breakDown = getNewVOldBD(emp, month)
        for i in range(0, 8):
            chartData[i]['dataPoints'] += [{ 'label': str(month), 'y': breakDown[intToModeConversion[i]], 'name': str(iTMSConv[i]) },]
    return chartData

def leaderboard_nvo_data(empName):
    emp = Employer.objects.get(name__exact=empName)
    return getCanvasJSChart(emp, new=True)

def leaderboard_reply_data(vol_v_perc, month, svs, sos, focusEmployer=None):
    topEmps = getTopCompanies(vol_v_perc, month, svs, sos)

    if focusEmployer is None and len(topEmps) > 0:
        focusEmployer = topEmps[0]
        emp = Employer.objects.get(name=focusEmployer[0])
    elif type(focusEmployer) is str:
        emp = Employer.objects.get(name=focusEmployer)
    elif type(focusEmployer) is Employer:
        emp = focusEmployer
    reply_data = {
            'chart_data': getCanvasJSChart(emp),
            'top_companies': topEmps,
            'checkin_matrix': getEmpCheckinMatrix(emp),
            'total_breakdown': getBreakDown(emp, "all"),
            'vol_v_perc': vol_v_perc,
            'month': month,
            'svs': svs,
            'sos': sos,
            'emp_sector': emp.sector.name,
            }
    if emp.size_cat is not None:
        reply_data['emp_size_cat'] = emp.size_cat.name
    return reply_data

def leaderboard_company_detail(empName):
    emp = Employer.objects.get(name=empName)
    reply_data = {
            'chart_data': getCanvasJSChart(emp),
            'checkin_matrix': getEmpCheckinMatrix(emp),
            'total_breakdown': getBreakDown(emp, "all"),
            'emp_sector': emp.sector.name,
            }
    if emp.size_cat is not None:
        reply_data['emp_size_cat'] = emp.size_cat.name
    return reply_data

def leaderboard_context():
    context = {
            'sectors': sorted(EmplSector.objects.all(), key=getSectorNum),
            'months': Month.objects.filter(active=True).order_by('-id'),
            }
    return context

def leaderboard(request):
    emps = Employer.objects.all()
    if request.method == "POST":
        if request.POST['just_emp'] == 'false':
            reply_data = leaderboard_reply_data(request.POST['selVVP'], request.POST['selMonth'], request.POST['selSVS'], request.POST['selSOS'],)
        elif request.POST['just_emp'] == 'true':
            reply_data = leaderboard_company_detail(request.POST['focusEmployer'])
        response = HttpResponse(json.dumps(reply_data), content_type='application/json')
        return response
    else:
        context = leaderboard_context()
        return render(request, 'leaderboard/leaderboard_js.html', context)

def leaderboard_bare(request, vol_v_perc='all', month='all', svs='all', sos='1', focusEmployer=None):
    context = leaderboard_context(request, vol_v_perc, month, svs, sos, focusEmployer)
    return render(request, 'leaderboard/leaderboard_bare.html', context)

def testchart(request):
    context = { 'CHART_DATA': getCanvasJSChart(Employer.objects.get(name="Dana-Farber Cancer Institute")) }
    return render(request, 'leaderboard/testchart.html', context)

def from_work_normally(survey):
    longest_dur = 0
    longest_mode = ''
    for leg in survey.legs:
        if not leg.duration and leg.day == 'n' and leg.direction == 'fw':
            longest_mode = leg.mode
        elif leg.duration > longest_dur and leg.day == 'n' and leg.direction == 'fw':
            longest_dur = leg.duration
            longest_mode = leg.mode
    if longest_mode == 'da':
        longest_mode == 'c'

    return longest_mode

def to_work_normally(survey):
    longest_dur = 0
    longest_mode = ''
    for leg in survey.legs:
        if not leg.duration and leg.day == 'n' and leg.direction == 'tw':
            longest_mode = leg.mode
        elif leg.duration > longest_dur and leg.day == 'n' and leg.direction == 'tw':
            longest_dur = leg.duration
            longest_mode = leg.mode
    if longest_mode == 'da':
        longest_mode == 'c'
    return longest_mode
   
def from_work_today(survey):
    longest_dur = 0
    longest_mode = ''
    for leg in survey.legs:
        if not leg.duration and leg.day == 'w' and leg.direction == 'fw':
            longest_mode = leg.mode
        elif leg.duration > longest_dur and leg.day == 'w' and leg.direction == 'fw':
            longest_dur = leg.duration
            longest_mode = leg.mode
    
    if longest_mode == 'da':
        longest_mode == 'c'

    return longest_mode

def to_work_today(survey):
    longest_dur = 0
    longest_mode = ''
    for leg in survey.legs:
        if not leg.duration and leg.day == 'w' and leg.direction == 'tw':
            longest_mode = leg.mode
        elif leg.duration > longest_dur and leg.day == 'w' and leg.direction == 'tw':
            longest_dur = leg.duration
            longest_mode = leg.mode
    if longest_mode == 'da':
        longest_mode == 'c'

    return longest_mode

def numNewCheckins(company, month1, month2):
    month1Checkins = Commutersurvey.objects.filter(employer=company, month=month1)
    month2Checkins = Commutersurvey.objects.filter(employer=company, month=month2)
    month1emails = []
    newCount = 0
    for checkin in month1Checkins:
        month1emails += checkin.email
    for checkin in month2Checkins:
        if checkin.email not in month1emails:
            newCount += 1
            month1emails += checkin.email
    return str(round(((newCount*1.0)/(len(month1emails)*1.0))*100, 2)) + "%"

def nvobreakdown(request, selEmpID=None):
    if selEmpID is None:
        context = {'emps': Employer.objects.all()}
        return render(request, 'leaderboard/chooseEmp.html', context)
    else:
        selEmp = Employer.objects.get(id=selEmpID)
        context = {'CHART_DATA': getCanvasJSChart(selEmp, new=True), 'emp': selEmp}
        return render(request, 'leaderboard/nvobreakdown.html', context)
