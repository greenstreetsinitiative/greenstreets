# Create your views here.
from survey.models import Commutersurvey, Employer, EmplSector, Leg
from leaderboard.models import Month, getMonths
from django.shortcuts import render, get_object_or_404
from django.http import HttpResponse
from operator import itemgetter, attrgetter
import json
from django.shortcuts import redirect

COLOR_SCHEME = {
        'gs': '#0096FF',
        'gc': '#65AB4B',
        'cc': '#FF2600',
        'us': '#9437FF',
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
    reply_data = leaderboard_reply_data('perc', 'August 2013', 'sector', '2');
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
    return redirect(url, permanent=True)

def new_leaderboard(request, empid=0, filter_by='sector', _filter=0, sort='participation'):
#    context = leaderboard_reply_data('perc', 'August 2013', filter_by, _filter);
    context = {}
    context['empid'] = empid
    
    if empid != 0:
        res = Employer.objects.filter(id=empid)
        emp = res[0]
        sector = emp.sector
    if empid != 0 and _filter == 0:
        _filter = sector

    context['filter_by'] = filter_by
    context['filt'] = _filter
    context['sort'] = sort
    context['sectors'] = sorted(EmplSector.objects.all(), key=getSectorNum)
    context['subteams'] = get_subteams()
    context['months'] = Month.objects.filter(active=True).order_by('-id')
    if sort == 'gs':
        context['ranks'] = green_switch_rankings(filter_by, _filter)
        context['ranks_pct'] = rankings_by_pct(filter_by, _filter)
    elif sort == 'gc':
        context['ranks'] = gc_rankings(filter_by, _filter)
        context['ranks_pct'] = gc_by_pct(filter_by, _filter)
    else:
        context['ranks'] = participation_rankings(filter_by, _filter)
        context['ranks_pct'] = participation_pct(filter_by, _filter)

    context['total_companies'] = len(context['ranks_pct'])
    context['total'] = 0
    for rank in context['ranks']:
        context['total'] += rank['val']
    
    if _filter == 0:
        context['emp_sector'] = 'all sectors'
    elif filter_by == 'sector' and empid == 0:
        sector = EmplSector.objects.filter(id=_filter)
        context['emp_sector'] = sector[0]
    if empid != 0:
        context['chart'] = json.dumps(getCanvasJSChart(emp) )
        emp_stats = getBreakDown(emp, 'August 2013')
        nsurveys = emp.get_surveys(month='August 2013').count()
        context['participation'] = ( float(nsurveys) / float(emp.nr_employees) ) * 100
        context['ncommutes'] = nsurveys*2
        context['gc'] = emp_stats['gc']
        context['gs'] = emp_stats['gs']
        context['cc'] = emp_stats['cc']
        context['other'] = emp_stats['us']
        context['gc_pct'] = ( ( emp_stats['gc']*1.0) / (nsurveys*2.0) ) * 100
        context['gs_pct'] = ( ( emp_stats['gs']*1.0) / (nsurveys*2.0) ) * 100
        context['stats'] = emp_stats
        context['employer'] = emp
        context['emp_sector'] = emp.sector
        context['m'] = getEmpCheckinMatrix(emp)
   
    return render(request, 'leaderboard/leaderboard_js.html', context)

def getSectorNum(sector):
    if sector.name[1] == ' ':
        return int(sector.name[0])
    elif sector.name[2] == ' ':
        return int(sector.name[:2])
    else:
        return int(sector.name[:3])

def get_subteams():
    sectors = sorted(EmplSector.objects.all(), key=getSectorNum)
    subteams = []
    for sector in sectors:
        words = sector.name.split()
        if int(words[0]) > 10:
            subteams.append(sector)

    return subteams

def getTopCompanies(vvp, month, svs, sos):
    emps = Employer.objects.filter(sector__in=EmplSector.objects.filter(parent=None))
    if svs == 'size':
        emps = emps.filter(size_cat=sos)
    elif svs == 'sector':
        sector = EmplSector.objects.get(pk=sos)
        if sector.parent != None:
            emps = Employer.objects.filter(sector=sos)
        else:
            emps = emps.filter(sector=sos)
    elif svs == 'name':
        nameList = []
        for emp in sorted(emps, key=attrgetter('name')):
            nameList += [(emp.name, 0, 0, emp.nr_employees),]
        return nameList
    companyList = []
    if vvp == 'perc':
        for company in emps:
            try:
                percent = (100 * float(company.get_nr_surveys(month))/float(company.nr_employees))
                if month == 'all':
                    percent /= len(getMonths())
                companyList += [(company.name, percent, ('%.1f' % percent), company.nr_employees),]
            except TypeError:
                pass
    else:
        for company in emps:
            nr_surveys = company.get_nr_surveys(month)
            companyList += [(company.name, nr_surveys, str(nr_surveys), company.nr_employees),]
    topEmps = sorted(companyList, key=itemgetter(1), reverse=True)
    return topEmps

def getEmpCheckinMatrix(emp):

    checkinMatrix = {}
    modes = [ 'c', 'cp', 'dalt', 'w', 'b', 'r', 't', 'o', 'tc' ]
    for mode in modes:
        checkinMatrix[mode] = {}
        for mode2 in modes:
            checkinMatrix[mode][mode2] = 0

    empCommutes = emp.get_surveys('all')
    for emp in empCommutes:
        if from_work_normally(emp) and from_work_today(emp) and to_work_normally(emp) and to_work_today(emp):
            checkinMatrix[from_work_today(emp)][from_work_normally(emp)] += 1
            checkinMatrix[to_work_today(emp)][to_work_normally(emp)] += 1
    print checkinMatrix
    return checkinMatrix

def participation_rankings(filter_by, _filter=0):
    rank = []
    pct = 0.0
    participation = 0.0
    if _filter == 0 and filter_by == 'sector':
        employers = Employer.objects.filter(active=True)
    elif filter_by == 'sector':
        employers = Employer.objects.filter(sector=_filter, active=True)

    if _filter == 0 and filter_by == 'size':
        employers = Employer.objects.filter(active=True)
    elif filter_by == 'size':
        employers = Employer.objects.filter(size_cat=_filter, active=True)

    for emp in employers:
        nsurveys = emp.get_surveys(month='August 2013').count()
        rank.append({'val': nsurveys, 'name': emp.name, 'id': emp.id })
    
    return sorted(rank, key=lambda idx: idx['val'], reverse=True);

def participation_pct(filter_by, _filter=0):
    rank = []
    pct = 0.0
    participation = 0.0
    if _filter == 0 and filter_by == 'sector':
        employers = Employer.objects.filter(active=True)
    elif filter_by == 'sector':
        employers = Employer.objects.filter(sector=_filter, active=True)

    if _filter == 0 and filter_by == 'size':
        employers = Employer.objects.filter(active=True)
    elif filter_by == 'size':
        employers = Employer.objects.filter(size_cat=_filter, active=True)

    for emp in employers:
        nsurveys = emp.get_surveys(month='August 2013').count()
        if not emp.nr_employees:
            continue
        participation = ( (nsurveys*1.0) / (emp.nr_employees*1.0) ) * 100
        rank.append({'pct': participation, 'name': emp.name, 'id': emp.id })
    
    return sorted(rank, key=lambda idx: idx['pct'], reverse=True);


def rankings_by_pct(filter_by, _filter=0):
    rank = []
    pct = 0.0
    if _filter == 0 and filter_by == 'sector':
        employers = Employer.objects.filter(active=True)
    elif filter_by == 'sector':
        employers = Employer.objects.filter(sector=_filter, active=True)

    if _filter == 0 and filter_by == 'size':
        employers = Employer.objects.filter(active=True)
    elif filter_by == 'size':
        employers = Employer.objects.filter(size_cat=_filter, active=True)

    for emp in employers:
        breakdown = getBreakDown(emp, 'August 2013')
        total = Employer.get_nr_surveys(emp, 'August 2013')
        if total == 0:
            pct = 0
        else:
            pct = ( (breakdown['gs']*1.0) / (total*2.0) ) * 100
        rank.append({'pct' : pct, 'name' : emp.name, 'id' : emp.id })

    return sorted(rank, key=lambda idx: idx['pct'], reverse=True);


def green_switch_rankings(filter_by, _filter=0):

    rank = []
    if filter_by == 'sector' and _filter == 0:
        employers = Employer.objects.filter(active=True)
    elif filter_by == 'sector':
        employers = Employer.objects.filter(sector=_filter, active=True)
    
    if filter_by == 'size' and _filter == 0:
        employers = Employer.objects.filter(active=True)
    elif filter_by == 'size':
        employers = Employer.objects.filter(size_cat=_filter, active=True)

    for emp in employers:
        breakdown = getBreakDown(emp, 'August 2013')
        rank.append({'val' : breakdown['gs'], 'name' : emp.name, 'id' : emp.id })

    return sorted(rank, key=lambda idx: idx['val'], reverse=True);

def gc_by_pct(filter_by, _filter=0):
    rank = []
    pct = 0.0
    if _filter == 0 and filter_by == 'sector':
        employers = Employer.objects.filter(active=True)
    elif filter_by == 'sector':
        employers = Employer.objects.filter(sector=_filter, active=True)

    if _filter == 0 and filter_by == 'size':
        employers = Employer.objects.filter(active=True)
    elif filter_by == 'size':
        employers = Employer.objects.filter(size_cat=_filter, active=True)

    for emp in employers:
        breakdown = getBreakDown(emp, 'August 2013')
        total = Employer.get_nr_surveys(emp, 'August 2013')
        if total == 0:
            pct = 0
        else:
            pct = ( (breakdown['gc']*1.0) / (total*2.0) ) * 100
        rank.append({'pct' : pct, 'name' : emp.name, 'id' : emp.id })

    return sorted(rank, key=lambda idx: idx['pct'], reverse=True);


def gc_rankings(filter_by, _filter=0):

    rank = []
    if filter_by == 'sector' and _filter == 0:
        employers = Employer.objects.filter(active=True)
    elif filter_by == 'sector':
        employers = Employer.objects.filter(sector=_filter, active=True)
    
    if filter_by == 'size' and _filter == 0:
        employers = Employer.objects.filter(active=True)
    elif filter_by == 'size':
        employers = Employer.objects.filter(size_cat=_filter, active=True)

    for emp in employers:
        breakdown = getBreakDown(emp, 'August 2013')
        rank.append({'val' : breakdown['gc'], 'name' : emp.name, 'id' : emp.id })

    return sorted(rank, key=lambda idx: idx['val'], reverse=True);

breakdown = {}

def getBreakDown(emp, month):
    global breakdown
    if emp.name in breakdown:
        return breakdown[emp.name]

    empSurveys = emp.get_surveys(month)
    unhealthySwitches = 0
    carCommuters = 0
    greenCommuters = 0
    greenSwitches = 0
    newUS = 0
    newCC = 0
    newGC = 0
    newGS = 0
    for survey in empSurveys:
        #if survey.email not i
        if survey.to_work_switch == 1:
            unhealthySwitches += 1
        elif survey.to_work_switch == 2:
            carCommuters += 1
        elif survey.to_work_switch == 3:
            greenCommuters += 1
        elif survey.to_work_switch == 4:
            greenSwitches += 1
        if survey.from_work_switch == 1:
            unhealthySwitches += 1
        elif survey.from_work_switch == 2:
            carCommuters += 1
        elif survey.from_work_switch == 3:
            greenCommuters += 1
        elif survey.from_work_switch == 4:
            greenSwitches += 1

    breakdown[emp.name] = { 'us': unhealthySwitches, 'cc': carCommuters, 'gc': greenCommuters, 'gs': greenSwitches, 'total':(len(empSurveys)*2) }

    return { 'us': unhealthySwitches, 'cc': carCommuters, 'gc': greenCommuters, 'gs': greenSwitches, 'total':(len(empSurveys)*2) }

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
    intToModeConversion = ['gs', 'gc', 'cc', 'us']
    iTMSConv = ['Green Switches','Green Commutes', 'Car Commutes', 'Other']
    for month in Month.objects.filter(active=True).order_by('id'):
        breakDown = getBreakDown(emp, month.month)
        for i in range(0, 4):
            chartData[i]['dataPoints'] += [{ 'label': month.short_name, 'y': breakDown[intToModeConversion[i]], 'name': iTMSConv[i] },]
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
    for month in reversed(getMonths()):
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
