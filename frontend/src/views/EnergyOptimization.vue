<script setup>
/**
 * EnergyOptimization.vue - 能耗优化·水墨意境
 *
 * 设计哲学：
 * - 留白：空白是意境的延伸
 * - 墨分五色：焦浓重淡清
 * - 气韵生动：数据亦有神韵
 * - 虚实相生：科技与传统融合
 */
import { ref, computed, reactive, onMounted, onUnmounted, nextTick } from 'vue'
import * as echarts from 'echarts'
import { getEnergyMetrics, getTimeBreakdown, getGpuEfficiency, getPowerPrediction, getCarbonData, runOptimize, getScheduleHistory, getHistoryComparison, exportEnergyReport, getAiInsight, getAiAnomalies, getSchedulerStatus, healthCheck } from '../services/api'
import { exportTextFile } from '../services/desktopExport'
import WorkspaceTabs from '../components/workspace/WorkspaceTabs.vue'

// ========== 数据 ==========
const activeTab = ref('overview')
const metrics = ref(null), breakdown = ref(null), efficiency = ref(null)
const prediction = ref(null), carbon = ref(null)
const scheduleHistory = ref(null), historyComparison = ref(null)
const optimizeResult = ref(null), optimizing = ref(false), loading = ref(true), exporting = ref(false)
const exportFeedback = ref(null)

// AI能力数据
const hasLlm = ref(false), aiInsight = ref(null), aiAnomalies = ref(null)
const aiAnomaliesLoading = ref(false), aiInsightLoading = ref(false)
const sourceState = ref({ connected: false, simulated: false, gpu_count: 0 })
const schedulerState = ref({ budget: { enabled: false, total_power_budget: 1200, usage_pct: 0, remaining_power: 1200, is_exceeded: false } })
const energyTabs = [
  { key: 'overview', label: '总览', desc: '指标与优化入口' },
  { key: 'prediction', label: '预测与对比', desc: '预测、回放、效果对比' },
  { key: 'ai', label: 'AI 洞察', desc: '趋势解读与异常诊断' },
]

// 动画数字
const an = reactive({power:0, kwh:0, cost:0, co2:0, saving:0, score:0})
function anim(k, t, d=1400) {
  const s=an[k], df=t-s, t0=performance.now()
  ;(function step(n){const p=Math.min((n-t0)/d,1);an[k]=s+df*(1-Math.pow(1-p,3));if(p<1)requestAnimationFrame(step)})(t0)
}

// ECharts
const trendRef=ref(null), predRef=ref(null), effRef=ref(null), pieRef=ref(null), gaugeRef=ref(null), compRef=ref(null)
let charts={}; let timer=null
function ci(k,el){if(!el.value)return null;if(charts[k])return charts[k];charts[k]=echarts.init(el.value);return charts[k]}

// 计算
const tp = computed(()=>{
  const h=new Date().getHours()
  if((h>=9&&h<12)||(h>=14&&h<18)) return {label:'高峰',color:'#C41E3A',bg:'rgba(196,30,58,0.08)'}
  if(h>=22||h<6) return {label:'低谷',color:'#2E8B57',bg:'rgba(46,139,87,0.08)'}
  return {label:'平峰',color:'#4A6741',bg:'rgba(74,103,65,0.08)'}
})

const sourceLabel = computed(() => {
  if (!sourceState.value.connected) return '数据源离线'
  if (sourceState.value.simulated) return `模拟采集 · ${sourceState.value.gpu_count}卡`
  return `真实采集 · ${sourceState.value.gpu_count}卡`
})

const sourceDetail = computed(() => {
  if (!sourceState.value.connected) return '当前无法获取 Agent 数据，能耗分析可能中断。'
  if (sourceState.value.simulated) return '当前为演示模式，适合界面联调与流程演示。'
  if ((metrics.value?.gpu_count || 0) <= 1) return '当前为本机单卡治理演示，历史数据库已重建，统计会随采集时间逐步累积。'
  return '当前为多卡真实采集，可直接用于功率预算治理和能耗统计。'
})

const budgetLabel = computed(() => {
  const budget = schedulerState.value?.budget || {}
  if (!budget.enabled) return '预算治理关闭'
  if (budget.is_exceeded) return `预算超限 ${Math.abs(budget.remaining_power || 0).toFixed(1)}W`
  return `预算剩余 ${(budget.remaining_power || 0).toFixed(1)}W`
})

const sourceHint = computed(() => {
  const gpuCount = metrics.value?.gpu_count || 0
  if (gpuCount <= 1) return '单卡本机治理演示'
  return `${gpuCount} 卡集群`
})

const breakdownLegendData = computed(() => {
  const data = breakdown.value?.breakdown
  return [
    { name: '高峰', value: data?.peak?.pct || 0, color: '#C41E3A' },
    { name: '平峰', value: data?.normal?.pct || 0, color: '#5B8C7E' },
    { name: '低谷', value: data?.valley?.pct || 0, color: '#3A5F4B' },
  ]
})

// ========== 数据加载 ==========
async function loadData() {
  try {
    const [a,b,c,d,e,s] = await Promise.all([getEnergyMetrics(24),getTimeBreakdown(24),getGpuEfficiency(),getPowerPrediction(24),getCarbonData(24),getSchedulerStatus()])
    metrics.value=a.data; breakdown.value=b.data; efficiency.value=c.data; prediction.value=d.data; carbon.value=e.data
    schedulerState.value = s.data
  } catch(err) { console.error('能耗数据加载失败', err) }
  // 加载调度历史和历史对比（独立try，不阻塞主数据）
  try { scheduleHistory.value = (await getScheduleHistory(72)).data } catch {}
  try { historyComparison.value = (await getHistoryComparison(72)).data } catch {}
  // 检测LLM可用性 + 加载AI数据
  try {
    const h = await healthCheck()
    hasLlm.value = h.data?.llm_available || false
    sourceState.value = {
      connected: !!h.data?.agent_connected,
      simulated: !!h.data?.agent_info?.simulated,
      gpu_count: Number(h.data?.agent_info?.gpu_count || 0),
    }
  } catch {
    hasLlm.value = false
    sourceState.value = { connected: false, simulated: false, gpu_count: 0 }
  }
  if (hasLlm.value) {
    aiInsightLoading.value = true; aiAnomaliesLoading.value = true
    try { aiInsight.value = (await getAiInsight()).data } catch { aiInsight.value = null }
    aiInsightLoading.value = false
    try { aiAnomalies.value = (await getAiAnomalies()).data } catch { aiAnomalies.value = null }
    aiAnomaliesLoading.value = false
  }
  loading.value=false
  anim('power',metrics.value?.current_total_power||0)
  anim('kwh',metrics.value?.kwh||0)
  anim('cost',(metrics.value?.cost_cny||0)*30)
  anim('co2',carbon.value?.co2_kg||0)
  anim('saving',metrics.value?.saving_pct||0)
  anim('score',metrics.value?.efficiency_score||0)
  await nextTick(); renderAll()
}

async function doOptimize() {
  optimizing.value=true
  try{ optimizeResult.value=(await runOptimize()).data }
  catch(err){ console.error('优化分析失败', err) }
  optimizing.value=false
}

async function doExport(fmt='markdown') {
  exporting.value=true
  try {
    const res = await exportEnergyReport(24, fmt)
    const filename = fmt === 'html' ? 'energy-report.html' : 'energy-report.md'
    const mime = fmt === 'html' ? 'text/html; charset=utf-8' : 'text/markdown; charset=utf-8'
    const saved = await exportTextFile(res.data, { filename, mime })
    exportFeedback.value = {
      tone: 'ok',
      text: saved.path ? `报告已保存到 ${saved.path}` : `已开始下载 ${saved.filename}`,
    }
  } catch(err) {
    console.error('报告导出失败', err)
    exportFeedback.value = {
      tone: 'error',
      text: err?.message || '报告导出失败',
    }
  }
  exporting.value=false
}

// AI 诊断刷新
async function refreshAiAnomalies() {
  aiAnomaliesLoading.value = true
  try { aiAnomalies.value = (await getAiAnomalies()).data } catch { aiAnomalies.value = null }
  aiAnomaliesLoading.value = false
}

// ========== 水墨图表配色 ==========
const inkColors = {
  mountain: '#3A5F4B',   // 青绿山水
  water: '#5B8C7E',      // 碧水
  ink: '#2C2C2C',        // 浓墨
  lightInk: '#7A7A7A',   // 淡墨
  vermillion: '#C41E3A', // 朱砂
  gold: '#B8860B',       // 暗金
  paper: '#F8F5F0',      // 宣纸
}

function renderAll(){ renderGauge(); renderPie(); renderTrend(); renderPred(); renderEff(); renderComp() }

function renderGauge(){
  const c=ci('g',gaugeRef); if(!c) return
  c.setOption({ backgroundColor:'transparent', series:[{
    type:'gauge', startAngle:225, endAngle:-45, min:0, max:100,
    pointer:{show:false},
    progress:{show:true,roundCap:true,width:12,itemStyle:{color:new echarts.graphic.LinearGradient(0,0,1,0,[{offset:0,color:'#3A5F4B40'},{offset:1,color:'#3A5F4B'}])}},
    axisLine:{lineStyle:{width:12,color:[[1,'rgba(0,0,0,0.04)']]}},
    axisTick:{show:false},splitLine:{show:false},axisLabel:{show:false},title:{show:false},
    detail:{valueAnimation:true,fontSize:28,fontWeight:700,fontFamily:"'ZCOOL XiaoWei','Noto Serif SC',serif",color:'#2C2C2C',offsetCenter:[0,'0%'],formatter:v=>v.toFixed(1)+'%'},
    data:[{value:metrics.value?.saving_pct||0}],
  }]})
}

function renderPie(){
  const c=ci('p',pieRef); if(!c||!breakdown.value?.breakdown) return
  const b=breakdown.value.breakdown
  c.setOption({ backgroundColor:'transparent', series:[{
    type:'pie',radius:['50%','75%'],center:['50%','50%'],padAngle:3,itemStyle:{borderRadius:4},
    label:{show:false},
    emphasis:{label:{show:true,fontSize:13,fontFamily:"'ZCOOL XiaoWei',serif",color:'#2C2C2C'},itemStyle:{shadowBlur:12,shadowColor:'rgba(0,0,0,0.1)'}},
    data:[
      {value:b.peak?.pct||0,name:'高峰',itemStyle:{color:'#C41E3A'}},
      {value:b.normal?.pct||0,name:'平峰',itemStyle:{color:'#5B8C7E'}},
      {value:b.valley?.pct||0,name:'低谷',itemStyle:{color:'#3A5F4B'}},
    ],animationType:'scale',animationEasing:'elasticOut',
  }]})
}

function renderTrend(){
  const c=ci('t',trendRef); if(!c||!breakdown.value) return
  const h=breakdown.value.hourly||[], hrs=h.map(x=>x.hour+':00'), pws=h.map(x=>x.avg_power), uts=h.map(x=>x.avg_util)
  const areas=[]; let s=0
  for(let i=1;i<=h.length;i++){if(i===h.length||h[i].period!==h[s].period){const p=h[s].period;const cl=p==='peak'?'rgba(196,30,58,0.05)':p==='valley'?'rgba(58,95,75,0.05)':'rgba(91,140,126,0.04)';areas.push([{xAxis:hrs[s],itemStyle:{color:cl}},{xAxis:hrs[i-1]}]);s=i}}
  c.setOption({ backgroundColor:'transparent',
    tooltip:{trigger:'axis',backgroundColor:'rgba(248,245,240,0.97)',borderColor:'rgba(0,0,0,0.08)',textStyle:{color:'#2C2C2C',fontSize:12,fontFamily:"'ZCOOL XiaoWei',serif"},extraCssText:'border-radius:8px;box-shadow:0 8px 32px rgba(0,0,0,0.08)',
      formatter:ps=>{const hi=h.find(x=>x.hour+':00'===ps[0]?.axisValue);const pl=hi?.period==='peak'?'高峰':hi?.period==='valley'?'低谷':'平峰';const pc=hi?.period==='peak'?'#C41E3A':hi?.period==='valley'?'#3A5F4B':'#5B8C7E';let r=`<div style="color:#999;font-size:11px;margin-bottom:4px">${ps[0]?.axisValue} <b style="color:${pc}">${pl}</b></div>`;ps.forEach(p=>{r+=`<div style="display:flex;align-items:center;gap:6px;margin:2px 0"><span style="width:8px;height:3px;border-radius:2px;background:${p.color}"></span>${p.seriesName}: <b>${typeof p.value==='number'?p.value.toFixed(1):p.value}</b></div>`});return r},
    },
    legend:{data:['功耗','利用率'],textStyle:{color:'#999',fontSize:11,fontFamily:"'ZCOOL XiaoWei',serif"},top:4,right:10,itemWidth:16,itemHeight:3},
    grid:{left:52,right:52,top:36,bottom:30},
    xAxis:{type:'category',data:hrs,boundaryGap:false,axisLine:{lineStyle:{color:'rgba(0,0,0,0.06)'}},axisTick:{show:false},axisLabel:{color:'#999',fontSize:10,interval:1}},
    yAxis:[
      {type:'value',name:'W',nameTextStyle:{color:'#999',fontSize:10},axisLine:{show:false},axisTick:{show:false},axisLabel:{color:'#999',fontSize:10},splitLine:{lineStyle:{color:'rgba(0,0,0,0.04)',type:'dashed'}}},
      {type:'value',name:'%',max:100,nameTextStyle:{color:'#999',fontSize:10},axisLine:{show:false},axisTick:{show:false},axisLabel:{color:'#999',fontSize:10},splitLine:{show:false}},
    ],
    series:[
      {name:'功耗',type:'line',smooth:.4,symbol:'none',lineStyle:{width:2.5,color:'#3A5F4B'},areaStyle:{color:new echarts.graphic.LinearGradient(0,0,0,1,[{offset:0,color:'rgba(58,95,75,0.15)'},{offset:1,color:'transparent'}])},data:pws,markArea:{silent:true,data:areas}},
      {name:'利用率',type:'line',smooth:.4,symbol:'none',yAxisIndex:1,lineStyle:{width:1.5,color:'#C41E3A80',type:[6,4]},data:uts},
    ],animationDuration:1500,
  })
}

function renderPred(){
  const c=ci('pd',predRef); if(!c||!prediction.value) return
  const ps=prediction.value.predictions||[], hrs=ps.map(p=>p.hour+':00')
  c.setOption({ backgroundColor:'transparent',
    tooltip:{trigger:'axis',backgroundColor:'rgba(248,245,240,0.97)',borderColor:'rgba(0,0,0,0.08)',textStyle:{color:'#2C2C2C',fontSize:12,fontFamily:"'ZCOOL XiaoWei',serif"},extraCssText:'border-radius:8px;box-shadow:0 8px 32px rgba(0,0,0,0.08)',
      formatter:pms=>{const i=pms[0]?.dataIndex??0,p=ps[i];if(!p)return'';const algoColor=p.algorithm==='多项式'?'#C41E3A':p.algorithm==='线性回归'?'#B8860B':'#5B4B8C';return`<div style="color:#999;font-size:11px;margin-bottom:4px">${p.hour}:00 (${p.period==='peak'?'高峰':p.period==='valley'?'低谷':'平峰'})</div><div>预测: <b style="color:#5B4B8C">${p.predicted_power}W</b></div><div style="font-size:11px;color:#999">置信: ${p.lower_bound}W ~ ${p.upper_bound}W</div><div style="font-size:11px;margin-top:4px;padding-top:4px;border-top:1px solid rgba(0,0,0,0.06)"><span style="color:${algoColor};font-weight:600">${p.algorithm||'加权平均'}</span> <span style="color:#bbb;margin-left:6px">RMSE ${p.rmse??'—'}</span> <span style="color:#bbb;margin-left:6px">R² ${p.r_squared??'—'}</span></div>`},
    },
    grid:{left:52,right:20,top:16,bottom:30},
    xAxis:{type:'category',data:hrs,boundaryGap:false,axisLine:{lineStyle:{color:'rgba(0,0,0,0.06)'}},axisTick:{show:false},axisLabel:{color:'#999',fontSize:10,interval:3}},
    yAxis:{type:'value',name:'W',nameTextStyle:{color:'#999',fontSize:10},axisLine:{show:false},axisTick:{show:false},axisLabel:{color:'#999',fontSize:10},splitLine:{lineStyle:{color:'rgba(0,0,0,0.04)',type:'dashed'}}},
    series:[
      {name:'u',type:'line',smooth:.4,symbol:'none',lineStyle:{width:0},areaStyle:{color:'transparent'},data:ps.map(p=>p.upper_bound),stack:'b',z:1},
      {name:'l',type:'line',smooth:.4,symbol:'none',lineStyle:{width:0},areaStyle:{color:new echarts.graphic.LinearGradient(0,0,0,1,[{offset:0,color:'rgba(91,75,140,0.12)'},{offset:1,color:'rgba(91,75,140,0.02)'}])},data:ps.map(p=>p.lower_bound),stack:'b',z:1},
      {name:'预测',type:'line',smooth:.4,showSymbol:false,lineStyle:{width:2.5,color:'#5B4B8C'},itemStyle:{color:'#5B4B8C'},data:ps.map(p=>p.predicted_power),z:10},
    ],animationDuration:1800,
  })
}

function renderEff(){
  const c=ci('ef',effRef); if(!c||!efficiency.value) return
  const gs=[...efficiency.value].sort((a,b)=>a.score-b.score)
  const colors=gs.map(g=>g.score>=70?'#3A5F4B':g.score>=40?'#B8860B':'#C41E3A')
  c.setOption({ backgroundColor:'transparent',
    tooltip:{trigger:'axis',axisPointer:{type:'shadow'},backgroundColor:'rgba(248,245,240,0.97)',borderColor:'rgba(0,0,0,0.08)',textStyle:{color:'#2C2C2C',fontSize:12},extraCssText:'border-radius:8px',
      formatter:ps=>{const i=ps[0]?.dataIndex??0,g=gs[i];if(!g)return'';return`<b>GPU ${g.gpu_index}</b><br/>效率: <b style="color:${colors[i]}">${g.score.toFixed(1)}</b><br/><span style="font-size:11px;color:#999">利用率:${g.gpu_utilization}% 功耗:${g.power_usage.toFixed(0)}/${g.power_limit}W</span>`},
    },
    grid:{left:65,right:50,top:8,bottom:8},
    xAxis:{type:'value',max:100,axisLine:{show:false},axisTick:{show:false},axisLabel:{show:false},splitLine:{lineStyle:{color:'rgba(0,0,0,0.03)'}}},
    yAxis:{type:'category',data:gs.map(g=>`GPU ${g.gpu_index}`),inverse:true,axisLine:{show:false},axisTick:{show:false},axisLabel:{color:'#666',fontSize:12,fontWeight:500,fontFamily:"'ZCOOL XiaoWei',serif"}},
    series:[
      {type:'bar',barWidth:16,z:2,data:gs.map((g,i)=>({value:g.score,itemStyle:{color:new echarts.graphic.LinearGradient(0,0,1,0,[{offset:0,color:colors[i]+'15'},{offset:1,color:colors[i]}]),borderRadius:[0,4,4,0]}})),label:{show:true,position:'right',color:'#999',fontSize:12,fontFamily:"'JetBrains Mono',monospace",fontWeight:600}},
      {type:'bar',barWidth:16,z:1,silent:true,data:gs.map(()=>({value:100,itemStyle:{color:'rgba(0,0,0,0.02)',borderRadius:[0,4,4,0]}}))},
    ],animationDuration:1200,
  })
}

function renderComp(){
  const c=ci('cp',compRef); if(!c||!historyComparison.value) return
  const hc=historyComparison.value
  const bs=hc.baseline_series||[], as2=hc.actual_series||[], ss=hc.savings_series||[]
  if(!bs.length) return
  const labels=bs.map(p=>{const d=new Date(p.timestamp*1000);return `${d.getMonth()+1}/${d.getDate()} ${d.getHours()}:00`})
  const optTime=hc.optimization_time||0
  const optIdx=bs.findIndex(p=>p.timestamp>=optTime)
  const markData=optIdx>=0?[{xAxis:labels[optIdx]}]:[]
  c.setOption({ backgroundColor:'transparent',
    tooltip:{trigger:'axis',backgroundColor:'rgba(248,245,240,0.97)',borderColor:'rgba(0,0,0,0.08)',textStyle:{color:'#2C2C2C',fontSize:12,fontFamily:"'ZCOOL XiaoWei',serif"},extraCssText:'border-radius:8px;box-shadow:0 8px 32px rgba(0,0,0,0.08)'},
    legend:{data:['基线功耗','实际功耗','节省量'],textStyle:{color:'#999',fontSize:11,fontFamily:"'ZCOOL XiaoWei',serif"},top:4,right:10,itemWidth:16,itemHeight:3},
    grid:{left:52,right:20,top:36,bottom:30},
    xAxis:{type:'category',data:labels,boundaryGap:false,axisLine:{lineStyle:{color:'rgba(0,0,0,0.06)'}},axisTick:{show:false},axisLabel:{color:'#999',fontSize:10,interval:Math.max(1,Math.floor(labels.length/12))}},
    yAxis:{type:'value',name:'W',nameTextStyle:{color:'#999',fontSize:10},axisLine:{show:false},axisTick:{show:false},axisLabel:{color:'#999',fontSize:10},splitLine:{lineStyle:{color:'rgba(0,0,0,0.04)',type:'dashed'}}},
    series:[
      {name:'基线功耗',type:'line',smooth:.4,symbol:'none',lineStyle:{width:2,color:'#C41E3A',type:'dashed',opacity:0.7},data:bs.map(p=>p.power),markLine:{silent:true,symbol:'none',lineStyle:{color:'#3A5F4B',type:'dashed',width:1.5},data:markData.map(d=>({...d,label:{formatter:'优化点',color:'#3A5F4B',fontSize:10,fontFamily:"'ZCOOL XiaoWei',serif"}}))}},
      {name:'实际功耗',type:'line',smooth:.4,symbol:'none',lineStyle:{width:2.5,color:'#2E8B57'},areaStyle:{color:new echarts.graphic.LinearGradient(0,0,0,1,[{offset:0,color:'rgba(46,139,87,0.1)'},{offset:1,color:'transparent'}])},data:as2.map(p=>p.power)},
      {name:'节省量',type:'bar',barWidth:4,itemStyle:{color:'rgba(46,139,87,0.35)',borderRadius:[2,2,0,0]},data:ss.map(p=>p.saved)},
    ],animationDuration:1500,
  })
}

function formatTs(ts) {
  if(!ts)return'—'
  const d=new Date(ts*1000)
  return `${d.getMonth()+1}/${d.getDate()} ${String(d.getHours()).padStart(2,'0')}:${String(d.getMinutes()).padStart(2,'0')}`
}
function parseTarget(t) {
  try{const o=typeof t==='string'?JSON.parse(t):t;return o?.gpu_index!==undefined?`GPU${o.gpu_index} → ${o.power_limit||'—'}W`:'—'}catch{return'—'}
}
function parseEvaluation(log) {
  if(log.action!=='ai_evaluate') return null
  try{const t=typeof log.target==='string'?JSON.parse(log.target):log.target;return t?.evaluation||null}catch{return null}
}
function actionLabel(log) {
  if(log.action==='ai_evaluate') return '复盘'
  if(log.action==='set_power_limit') return '调频'
  if(log.action==='pause_task') return '暂停'
  if(log.action==='resume_task') return '恢复'
  if(log.action==='configure_budget') return '预算'
  return log.action || '未知动作'
}
function historyTargetLabel(log) {
  if(log.action==='ai_evaluate') return 'AI 调度复盘'
  try {
    const o = typeof log.target === 'string' ? JSON.parse(log.target) : log.target
    if(o?.gpu_index!==undefined) return `GPU${o.gpu_index} → ${o.power_limit||'—'}W`
    if(o?.pid!==undefined) return `PID ${o.pid}`
    if(o?.total_power_budget!==undefined) return `总预算 ${o.total_power_budget}W`
    return '—'
  } catch { return '—' }
}
function historyResultLabel(log) {
  if(log.action==='ai_evaluate') return '评估完成'
  return log.result==='success' ? '成功' : '失败'
}
function historyResultFail(log) {
  return log.action!=='ai_evaluate' && log.result==='failed'
}

function handleResize(){Object.values(charts).forEach(c=>c?.resize())}
onMounted(()=>{loadData();timer=setInterval(loadData,30000);window.addEventListener('resize',handleResize)})
onUnmounted(()=>{clearInterval(timer);window.removeEventListener('resize',handleResize);Object.values(charts).forEach(c=>c?.dispose());charts={}})
</script>

<template>
<div class="ink-page">
  <!-- 背景水墨装饰 -->
  <div class="ink-bg">
    <div class="ink-mountain"></div>
    <div class="ink-cloud ink-cloud--1"></div>
    <div class="ink-cloud ink-cloud--2"></div>
  </div>

  <!-- 加载 -->
  <div v-if="loading" class="ink-loading">
    <div class="ink-loading__brush"></div>
    <div class="ink-loading__text">墨韵加载中...</div>
  </div>

  <template v-else>
    <!-- ===== 页头题字 ===== -->
    <header class="ink-header si" style="--d:0s">
      <div class="ink-header__left">
        <h1 class="ink-title">能耗治理</h1>
        <p class="ink-subtitle">真实采集 · 预算联动 · 绿色治理</p>
      </div>
      <div class="ink-header__right">
        <button class="seal-btn seal-btn--sm" :disabled="exporting" @click="doExport('markdown')">
          <span class="seal-btn__stamp seal-btn__stamp--sm">报</span>
          <span class="seal-btn__text seal-btn__text--sm">{{ exporting ? '...' : '导出报告' }}</span>
        </button>
        <span
          class="ink-period"
          :style="{
            color: schedulerState?.budget?.is_exceeded ? '#C41E3A' : schedulerState?.budget?.enabled ? '#2E8B57' : '#666',
            background: schedulerState?.budget?.is_exceeded ? 'rgba(196,30,58,0.08)' : schedulerState?.budget?.enabled ? 'rgba(46,139,87,0.08)' : 'rgba(0,0,0,0.04)',
          }"
        >
          {{ budgetLabel }}
        </span>
        <span class="ink-period" :style="{color:tp.color,background:tp.bg}">{{ tp.label }}时段</span>
      </div>
      <!-- 印章 -->
      <div class="ink-seal">
        <span>智<br/>能</span>
      </div>
    </header>

    <section class="source-strip si" style="--d:.05s">
      <div class="source-card">
        <div class="source-card__label">当前数据源</div>
        <div class="source-card__value">{{ sourceLabel }}</div>
        <div class="source-card__hint">{{ sourceDetail }}</div>
      </div>
      <div class="source-card">
        <div class="source-card__label">预算治理状态</div>
        <div class="source-card__value">{{ budgetLabel }}</div>
        <div class="source-card__hint">
          {{ schedulerState?.budget?.enabled ? `当前预算上限 ${schedulerState.budget.total_power_budget}W，可与任务优先级联动治理。` : '当前以监测为主，可在调度页开启功率预算治理。' }}
        </div>
      </div>
      <div class="source-card">
        <div class="source-card__label">演示说明</div>
        <div class="source-card__value">{{ sourceHint }}</div>
        <div class="source-card__hint">当前页面全部基于本地 Agent 实时采集，不再引用旧虚拟样例数据。</div>
      </div>
    </section>

    <section
      v-if="exportFeedback"
      class="ink-export-feedback si"
      style="--d:.08s"
      :class="`ink-export-feedback--${exportFeedback.tone}`"
    >
      {{ exportFeedback.text }}
    </section>

    <WorkspaceTabs v-model="activeTab" :items="energyTabs" />

    <!-- ===== KPI 六宫格 ===== -->
    <div v-if="activeTab === 'overview'" class="kpi-grid si" style="--d:.1s">
      <div class="kpi-ink kpi-ink--hero">
        <div class="kpi-ink__brush"></div>
        <div class="kpi-ink__label">实时总功耗</div>
        <div class="kpi-ink__big stat-value">{{ an.power.toFixed(0) }}<span class="kpi-ink__unit">W</span></div>
        <div class="kpi-ink__hint">{{ sourceHint }}</div>
      </div>
      <div class="kpi-ink">
        <div class="kpi-ink__label">日能耗</div>
        <div class="kpi-ink__val stat-value">{{ an.kwh.toFixed(1) }}<span class="kpi-ink__unit">kWh</span></div>
        <div class="kpi-ink__hint">{{ metrics?.hours||24 }}h 累计</div>
      </div>
      <div class="kpi-ink">
        <div class="kpi-ink__label">月预估费用</div>
        <div class="kpi-ink__val stat-value" style="color:#B8860B">¥{{ an.cost.toFixed(0) }}</div>
        <div class="kpi-ink__hint">¥0.85/kWh 商业电价</div>
      </div>
      <div class="kpi-ink">
        <div class="kpi-ink__label">今日碳排放</div>
        <div class="kpi-ink__val stat-value" style="color:#3A5F4B">{{ an.co2.toFixed(2) }}<span class="kpi-ink__unit">kg</span></div>
        <div class="kpi-ink__hint" style="color:#3A5F4B">≈ {{ carbon?.trees_equivalent?.toFixed(1)||'0' }} 棵树/天</div>
      </div>
      <div class="kpi-ink">
        <div class="kpi-ink__label">节能比例</div>
        <div class="kpi-ink__val stat-value" :style="{color:an.saving>=20?'#2E8B57':'#3A5F4B'}">{{ an.saving.toFixed(1) }}<span class="kpi-ink__unit">%</span></div>
        <div class="kpi-ink__bar"><div class="kpi-ink__bar-f" :style="{width:Math.min(an.saving,100)+'%'}"></div></div>
      </div>
      <div class="kpi-ink">
        <div class="kpi-ink__label">效率评分</div>
        <div class="kpi-ink__val stat-value" :style="{color:an.score>=70?'#2E8B57':an.score>=40?'#B8860B':'#C41E3A'}">{{ an.score.toFixed(0) }}<span class="kpi-ink__unit">分</span></div>
        <div class="kpi-ink__bar"><div class="kpi-ink__bar-f" :style="{width:Math.min(an.score,100)+'%',background:an.score>=70?'#3A5F4B':an.score>=40?'#B8860B':'#C41E3A'}"></div></div>
      </div>
    </div>

    <!-- ===== D2: AI 趋势洞察 ===== -->
    <div v-if="activeTab === 'ai' && hasLlm" class="ink-card ink-card--wide ink-card--ai si" style="--d:.12s">
      <div class="ink-card__hd">
        <div class="ink-card__title-group">
          <span class="ink-card__eyebrow">趋势分析 · 风险研判</span>
          <span class="ink-card__title">AI 趋势洞察</span>
        </div>
        <span class="ink-stamp ink-stamp--ai">智</span>
        <span v-if="aiInsight" class="ai-risk-badge" :class="'ai-risk-badge--'+aiInsight.risk_level">{{ {low:'低风险',medium:'中风险',high:'高风险'}[aiInsight.risk_level]||'--' }}</span>
      </div>
      <!-- 加载态 -->
      <div v-if="aiInsightLoading" class="ai-loading-box">
        <div class="ai-loading-box__brush"></div>
        <span class="ai-loading-box__text">AI 正在分析趋势...</span>
      </div>
      <!-- 内容态 -->
      <div v-else-if="aiInsight" class="ai-insight-body">
        <div class="ai-insight-summary">{{ aiInsight.summary }}</div>
        <div class="ai-insight-detail">{{ aiInsight.detail }}</div>
        <div v-if="aiInsight.suggestions?.length" class="ai-insight-suggestions">
          <span v-for="(s,i) in aiInsight.suggestions" :key="i" class="ai-insight-sug">{{ s }}</span>
        </div>
      </div>
      <!-- 空态 -->
      <div v-else class="ai-empty-hint">暂无趋势洞察数据，请稍后重试。</div>
    </div>

    <!-- ===== 三栏：节能仪表 / 碳排放 / 时段分布 ===== -->
    <div v-if="activeTab === 'overview'" class="tri-grid si" style="--d:.2s">
      <div class="ink-card">
        <div class="ink-card__hd"><span class="ink-card__title">节能仪表</span><span class="ink-stamp ink-stamp--green">节</span></div>
        <div ref="gaugeRef" style="height:190px;margin:-10px 0"></div>
        <div class="gauge-bottom">
          <div><div class="gauge-bottom__l">日节省</div><div class="gauge-bottom__v stat-value">{{ metrics?(metrics.kwh*metrics.saving_pct/100).toFixed(2):'0' }} kWh</div></div>
          <div class="gauge-bottom__sep"></div>
          <div><div class="gauge-bottom__l">月节省</div><div class="gauge-bottom__v stat-value">¥{{ metrics?(metrics.cost_cny*30*metrics.saving_pct/100).toFixed(0):'0' }}</div></div>
        </div>
      </div>
      <div class="ink-card">
        <div class="ink-card__hd"><span class="ink-card__title">碳排放</span><span class="ink-stamp ink-stamp--teal">碳</span></div>
        <div class="carbon-row">
          <div class="carbon-item"><div class="carbon-item__v stat-value" style="color:#3A5F4B;font-size:1.75rem">{{ carbon?.co2_kg?.toFixed(2)||'—' }}</div><div class="carbon-item__l">kgCO₂ / 日</div></div>
          <div class="carbon-item"><div class="carbon-item__v stat-value" style="color:#2E8B57;font-size:1.75rem">{{ carbon?.trees_equivalent?.toFixed(1)||'—' }}</div><div class="carbon-item__l">🌳 等效树木</div></div>
        </div>
        <div class="carbon-meta"><span>碳因子 {{ carbon?.carbon_factor||'0.5703' }}</span><span>已减排 <b style="color:#2E8B57">{{ carbon?.co2_saved_kg?.toFixed(3)||'0' }}</b> kg</span></div>
      </div>
      <div class="ink-card">
        <div class="ink-card__hd"><span class="ink-card__title">时段分布</span><span class="ink-period-sm" :style="{color:tp.color,background:tp.bg}">{{ tp.label }}</span></div>
        <div ref="pieRef" style="height:155px"></div>
        <div class="pie-legend">
          <div v-for="d in breakdownLegendData" :key="d.name" class="pie-legend__i">
            <span class="pie-legend__dot" :style="{background:d.color}"></span>
            <span class="pie-legend__name">{{ d.name }}</span>
            <span class="pie-legend__pct stat-value" :style="{color:d.color}">{{ d.value?.toFixed?.(1) || '0' }}%</span>
          </div>
        </div>
      </div>
    </div>

    <!-- ===== 功耗趋势（全宽） ===== -->
    <div v-if="activeTab === 'overview'" class="ink-card ink-card--wide si" style="--d:.3s">
      <div class="ink-card__hd">
        <span class="ink-card__title">廿四时功耗</span>
        <div class="trend-legend">
          <span class="trend-legend__i"><span class="trend-legend__bar" style="background:#C41E3A"></span>高峰</span>
          <span class="trend-legend__i"><span class="trend-legend__bar" style="background:#3A5F4B"></span>低谷</span>
          <span class="trend-legend__i"><span class="trend-legend__bar" style="background:#5B8C7E"></span>平峰</span>
        </div>
      </div>
      <div ref="trendRef" style="height:300px"></div>
    </div>

    <!-- ===== 预测 + 效率 ===== -->
    <div v-if="activeTab === 'prediction'" class="duo-grid si" style="--d:.4s">
      <div class="ink-card">
        <div class="ink-card__hd"><span class="ink-card__title">未来廿四时预测</span><span class="ink-stamp ink-stamp--purple">测</span></div>
        <div ref="predRef" style="height:280px"></div>
        <!-- D3: AI预测解读 -->
        <div v-if="hasLlm && prediction?.ai_interpretation" class="ai-interpret-box">
          <span class="ai-interpret-icon">智</span>
          <span class="ai-interpret-text">{{ prediction.ai_interpretation }}</span>
        </div>
      </div>
      <div class="ink-card">
        <div class="ink-card__hd"><span class="ink-card__title">效率评分</span><span class="ink-stamp ink-stamp--gold">效</span></div>
        <div ref="effRef" :style="{height:Math.max((efficiency?.length||4)*52+16,200)+'px'}"></div>
      </div>
    </div>

    <!-- ===== D1: AI 深度诊断 ===== -->
    <div v-if="activeTab === 'ai'" class="ink-card ink-card--wide ink-card--ai si" style="--d:.48s">
      <div class="ink-card__hd">
        <div class="ink-card__title-group">
          <span class="ink-card__eyebrow">异常模式识别 · 超越阈值告警</span>
          <span class="ink-card__title">AI 深度诊断</span>
        </div>
        <span class="ink-stamp ink-stamp--ai">诊</span>
        <template v-if="hasLlm && aiAnomalies">
          <span v-if="aiAnomalies.healthy && !aiAnomalies.anomalies?.length" class="ai-risk-badge ai-risk-badge--low">健康</span>
          <span v-else-if="aiAnomalies.anomalies?.length" class="ai-risk-badge ai-risk-badge--high">发现 {{ aiAnomalies.anomalies.length }} 项异常</span>
        </template>
        <button v-if="hasLlm" class="seal-btn seal-btn--sm" :disabled="aiAnomaliesLoading" @click="refreshAiAnomalies" style="margin-left:auto">
          <span class="seal-btn__stamp seal-btn__stamp--sm">{{ aiAnomaliesLoading ? '···' : '刷' }}</span>
          <span class="seal-btn__text seal-btn__text--sm">{{ aiAnomaliesLoading ? '诊断中...' : '刷新诊断' }}</span>
        </button>
      </div>

      <!-- LLM 未接入提示 -->
      <div v-if="!hasLlm" class="ai-empty-hint ai-empty-hint--llm">
        <div class="ai-empty-hint__icon">智</div>
        <div class="ai-empty-hint__text">接入 LLM 后可获得深度异常诊断能力。</div>
        <div class="ai-empty-hint__sub">当前仅使用基础阈值告警，配置大语言模型后可识别散热退化、周期性骤降、负载不均等隐患模式。</div>
      </div>

      <!-- 加载态 -->
      <div v-else-if="aiAnomaliesLoading" class="ai-loading-box">
        <div class="ai-loading-box__brush"></div>
        <span class="ai-loading-box__text">AI 正在进行深度诊断...</span>
      </div>

      <!-- 健康状态 -->
      <div v-else-if="aiAnomalies?.healthy && !aiAnomalies?.anomalies?.length" class="ai-healthy-box">
        <div class="ai-healthy-box__icon">安</div>
        <div class="ai-healthy-box__text">集群运行健康，未检测到隐患模式。</div>
        <div class="ai-healthy-box__sub">AI 已完成散热趋势、功耗周期、负载均衡、效率衰减等多维度扫描，当前各项指标正常。</div>
      </div>

      <!-- 异常列表 -->
      <div v-else-if="aiAnomalies?.anomalies?.length" class="ai-anomaly-list">
        <div v-for="(a,i) in aiAnomalies.anomalies" :key="i" class="ai-anomaly-item" :class="'ai-anomaly-item--'+a.severity">
          <div class="ai-anomaly-item__head">
            <span class="ai-anomaly-item__type">{{ a.type }}</span>
            <span v-if="a.gpu_index!==undefined" class="ai-anomaly-item__gpu">GPU {{ a.gpu_index }}</span>
            <span class="ai-anomaly-item__sev" :class="'ai-anomaly-item__sev--'+a.severity">{{ a.severity==='critical'?'严重':'警告' }}</span>
          </div>
          <div class="ai-anomaly-item__desc">{{ a.description }}</div>
          <div v-if="a.suggestion" class="ai-anomaly-item__sug">建议：{{ a.suggestion }}</div>
        </div>
      </div>

      <!-- 无数据态 -->
      <div v-else class="ai-empty-hint">暂无诊断数据，点击"刷新诊断"重新检测。</div>
    </div>

    <!-- ===== 一键优化 ===== -->
    <div v-if="activeTab === 'overview'" class="ink-card ink-card--wide si" style="--d:.5s">
      <div class="ink-card__hd">
        <span class="ink-card__title">智能优化</span>
        <button class="seal-btn" :disabled="optimizing" @click="doOptimize">
          <span class="seal-btn__stamp">{{ optimizing ? '···' : '优' }}</span>
          <span class="seal-btn__text">{{ optimizing ? '运筹帷幄中...' : '一键智能优化' }}</span>
        </button>
      </div>

      <div v-if="!optimizeResult&&!optimizing" class="opt-empty-ink">
        <div class="opt-empty-ink__char">道</div>
        <div class="opt-empty-ink__t">静待妙策</div>
        <div class="opt-empty-ink__d">基于实时集群状态、时段电价、负载特征<br/>AI 将运筹帷幄，为您量身定制节能方案</div>
      </div>

      <div v-if="optimizeResult" class="opt-result-ink">
        <div class="opt-compare">
          <div class="opt-compare__item">
            <div class="opt-compare__label">优化前</div>
            <div class="opt-compare__val stat-value" style="color:#C41E3A">{{ optimizeResult.baseline_power?.toFixed(0)||'—' }}<span class="opt-compare__u">W</span></div>
          </div>
          <div class="opt-compare__arrow">
            <svg width="48" height="24" viewBox="0 0 48 24"><path d="M2 12 H38 M32 6 L38 12 L32 18" stroke="#3A5F4B" stroke-width="2" fill="none" stroke-linecap="round"/></svg>
          </div>
          <div class="opt-compare__item">
            <div class="opt-compare__label">优化后</div>
            <div class="opt-compare__val stat-value" style="color:#2E8B57">{{ optimizeResult.optimized_power?.toFixed(0)||'—' }}<span class="opt-compare__u">W</span></div>
          </div>
          <div class="opt-compare__sep"></div>
          <div class="opt-compare__item">
            <div class="opt-compare__label">节省</div>
            <div class="opt-compare__val stat-value" style="color:#2E8B57;font-size:2.25rem">{{ optimizeResult.saving_pct?.toFixed(1)||'0' }}<span class="opt-compare__u" style="font-size:1rem">%</span></div>
            <div class="opt-compare__meta">-{{ optimizeResult.estimated_saving_w?.toFixed(0)||'0' }}W · ¥{{ optimizeResult.cost_saved_per_hour?.toFixed(3)||'0' }}/h</div>
          </div>
        </div>

        <div class="ink-card__title" style="margin:28px 0 16px">优化策略</div>
        <div class="sug-grid-ink">
          <div v-for="(s,i) in optimizeResult.suggestions||[]" :key="i" class="sug-ink si" :style="{'--d':i*.1+'s'}">
            <div class="sug-ink__seal">{{ ['壹','贰','叁','肆','伍','陆'][i]||i+1 }}</div>
            <div class="sug-ink__body">
              <div class="sug-ink__top">
                <span v-if="s.action&&s.action!=='none'" class="sug-ink__tag">{{ s.action==='set_power_limit'?'调频':s.action==='pause_task'?'暂停':s.action }}</span>
                <span v-if="s.target?.gpu_index!==undefined" class="sug-ink__gpu">GPU {{ s.target.gpu_index }}</span>
                <span v-if="s.target?.power_limit" class="sug-ink__tgt">→ {{ s.target.power_limit }}W</span>
                <span v-if="s.estimated_saving_w" class="sug-ink__save">-{{ typeof s.estimated_saving_w==='number'?s.estimated_saving_w.toFixed(0):s.estimated_saving_w }}W</span>
              </div>
              <div class="sug-ink__reason">{{ s.reason }}</div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- ===== F2: 优化效果对比（全宽） ===== -->
    <div v-if="activeTab === 'prediction'" class="ink-card ink-card--wide si" style="--d:.6s">
      <div class="ink-card__hd">
        <span class="ink-card__title">优化效果对比</span>
        <div class="trend-legend">
          <span class="trend-legend__i"><span class="trend-legend__bar" style="background:#C41E3A;border-style:dashed"></span>基线</span>
          <span class="trend-legend__i"><span class="trend-legend__bar" style="background:#2E8B57"></span>实际</span>
          <span class="trend-legend__i"><span class="trend-legend__bar" style="background:rgba(46,139,87,0.35);height:8px;border-radius:2px"></span>节省</span>
          <span v-if="historyComparison?.total_saved_kwh" class="comp-saved">累计节省 <b>{{ historyComparison.total_saved_kwh.toFixed(1) }}</b> kWh</span>
        </div>
      </div>
      <div ref="compRef" style="height:300px"></div>
    </div>

    <!-- ===== F4: 调度历史回放 ===== -->
    <div v-if="activeTab === 'prediction'" class="ink-card ink-card--wide si" style="--d:.7s">
      <div class="ink-card__hd">
        <span class="ink-card__title">调度历史</span>
        <span class="ink-stamp ink-stamp--green">调</span>
      </div>
      <div v-if="!scheduleHistory?.logs?.length" class="opt-empty-ink" style="padding:30px 20px 20px">
        <div class="opt-empty-ink__char" style="font-size:3rem">静</div>
        <div class="opt-empty-ink__d">暂无调度记录</div>
      </div>
      <div v-else class="schedule-timeline">
        <div class="sched-stats">
          <span>动作 <b>{{ scheduleHistory.execution_total ?? scheduleHistory.total }}</b> 次</span>
          <span style="color:#2E8B57">成功 <b>{{ scheduleHistory.success_count }}</b></span>
          <span style="color:#C41E3A">失败 <b>{{ scheduleHistory.failure_count ?? ((scheduleHistory.execution_total ?? scheduleHistory.total) - scheduleHistory.success_count) }}</b></span>
          <span style="color:#5B4B8C">AI复盘 <b>{{ scheduleHistory.evaluation_total || 0 }}</b></span>
        </div>
        <div class="timeline-list">
          <div v-for="log in scheduleHistory.logs" :key="log.id" class="timeline-item">
            <div class="timeline-dot" :class="{'timeline-dot--fail':historyResultFail(log)}"></div>
            <div class="timeline-line"></div>
            <div class="timeline-card">
              <div class="timeline-card__top">
                <span class="timeline-card__time">{{ formatTs(log.timestamp) }}</span>
                <span class="timeline-card__action" :class="{'timeline-card__action--ai':log.action==='ai_evaluate'}">{{ actionLabel(log) }}</span>
                <span class="timeline-card__target">{{ historyTargetLabel(log) }}</span>
                <span class="timeline-card__result" :class="{'timeline-card__result--fail':historyResultFail(log), 'timeline-card__result--neutral':log.action==='ai_evaluate'}">{{ historyResultLabel(log) }}</span>
              </div>
              <div class="timeline-card__reason">{{ log.reason }}</div>
              <!-- D4: AI调度评估 -->
              <div v-if="parseEvaluation(log)" class="ai-eval-inline">
                <span class="ai-eval-inline__score" :style="{color:parseEvaluation(log).score>=70?'#2E8B57':parseEvaluation(log).score>=40?'#B8860B':'#C41E3A'}">{{ parseEvaluation(log).score }}分</span>
                <span class="ai-eval-inline__verdict">{{ parseEvaluation(log).verdict }}</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 底部竖排文字装饰 -->
    <div class="ink-footer si" style="--d:.9s">
      <div class="ink-vert-text">绿色计算 · 智慧能源</div>
    </div>
  </template>
</div>
</template>

<style scoped>
@import url('https://fonts.googleapis.com/css2?family=Ma+Shan+Zheng&family=ZCOOL+XiaoWei&family=ZCOOL+KuaiLe&family=Noto+Serif+SC:wght@300;700&display=swap');

/* ===== 宣纸底色 & 水墨基调 ===== */
.ink-page {
  max-width: 1600px;
  margin: 0 auto;
  position: relative;
  color: #2C2C2C;
  font-family: 'ZCOOL XiaoWei', 'Noto Serif SC', serif;
}

.ink-export-feedback {
  margin: 0 0 18px;
  padding: 12px 16px;
  border-radius: 12px;
  border: 1px solid rgba(0,0,0,0.06);
  background: rgba(255,255,255,0.62);
  font-size: 0.8125rem;
  line-height: 1.7;
  color: #3A5F4B;
}

.ink-export-feedback--error {
  color: #C41E3A;
  border-color: rgba(196,30,58,0.16);
  background: rgba(196,30,58,0.06);
}

/* ===== 背景水墨山水 ===== */
.ink-bg {
  position: fixed;
  inset: 0;
  pointer-events: none;
  z-index: -1;
  overflow: hidden;
}

.ink-mountain {
  position: absolute;
  bottom: 0; left: 0; right: 0;
  height: 35%;
  background:
    linear-gradient(165deg, transparent 30%, rgba(58,95,75,0.03) 50%, rgba(58,95,75,0.06) 70%, rgba(58,95,75,0.04) 100%);
  filter: blur(1px);
  mask-image: linear-gradient(to top, rgba(0,0,0,0.6), transparent);
}

.ink-cloud {
  position: absolute;
  width: 400px; height: 80px;
  background: radial-gradient(ellipse, rgba(58,95,75,0.04) 0%, transparent 70%);
  filter: blur(20px);
  animation: cloud-drift 60s linear infinite;
}
.ink-cloud--1 { top: 15%; left: -200px; }
.ink-cloud--2 { top: 40%; left: -300px; animation-delay: -30s; animation-duration: 80s; }
@keyframes cloud-drift { from{transform:translateX(0)} to{transform:translateX(calc(100vw + 400px))} }

/* ===== 入场动画 ===== */
.si { animation: ink-rise .7s cubic-bezier(.16,1,.3,1) both; animation-delay: var(--d,0s); }
@keyframes ink-rise { from{opacity:0;transform:translateY(20px)} to{opacity:1;transform:translateY(0)} }

/* ===== 页头 ===== */
.ink-header {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  margin-bottom: 28px;
  padding-bottom: 16px;
  border-bottom: 1px solid rgba(0,0,0,0.06);
  position: relative;
}

.ink-title {
  font-family: 'Ma Shan Zheng', cursive;
  font-size: 2.5rem;
  font-weight: 400;
  letter-spacing: 0.15em;
  color: #1a1a1a;
  line-height: 1;
  margin-bottom: 6px;
}

.ink-subtitle {
  font-size: 0.8125rem;
  color: #999;
  letter-spacing: 0.3em;
}

.ink-header__right {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  justify-content: flex-end;
}

.ink-period {
  display: inline-flex;
  padding: 4px 14px;
  border-radius: 4px;
  font-size: 0.75rem;
  font-weight: 500;
  letter-spacing: 0.1em;
}

/* 印章 */
.ink-seal {
  position: absolute;
  top: -4px; right: 100px;
  width: 42px; height: 42px;
  border: 2.5px solid #C41E3A;
  border-radius: 4px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #C41E3A;
  font-family: 'ZCOOL KuaiLe', cursive;
  font-size: 0.8rem;
  line-height: 1.1;
  text-align: center;
  transform: rotate(-8deg);
  opacity: 0.7;
}

/* ===== KPI 六宫格 ===== */
.source-strip {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 14px;
  margin-bottom: 18px;
}

.source-card {
  padding: 16px 18px;
  background: rgba(255,255,255,0.56);
  border: 1px solid rgba(0,0,0,0.04);
  border-radius: 12px;
  backdrop-filter: blur(8px);
}

.source-card__label {
  font-size: 0.6875rem;
  color: #999;
  letter-spacing: 0.14em;
  margin-bottom: 8px;
}

.source-card__value {
  font-size: 1rem;
  color: #1f2937;
  font-weight: 700;
  margin-bottom: 6px;
}

.source-card__hint {
  font-size: 0.75rem;
  color: #666;
  line-height: 1.7;
}

.kpi-grid {
  display: grid;
  grid-template-columns: 1.5fr repeat(5, 1fr);
  gap: 14px;
  margin-bottom: 18px;
}

.kpi-ink {
  position: relative;
  padding: 20px 16px;
  background: rgba(255,255,255,0.6);
  border: 1px solid rgba(0,0,0,0.04);
  border-radius: 12px;
  backdrop-filter: blur(8px);
  transition: all .3s;
}

.kpi-ink:hover {
  background: rgba(255,255,255,0.8);
  box-shadow: 0 8px 32px rgba(0,0,0,0.04);
  transform: translateY(-2px);
}

.kpi-ink--hero {
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  background: linear-gradient(145deg, rgba(58,95,75,0.04), rgba(255,255,255,0.7));
  border-color: rgba(58,95,75,0.08);
  position: relative;
  overflow: hidden;
}

.kpi-ink__brush {
  position: absolute;
  top: 0; left: 0; right: 0; height: 3px;
  background: linear-gradient(90deg, transparent 5%, rgba(58,95,75,0.2) 20%, rgba(58,95,75,0.4) 40%, rgba(58,95,75,0.3) 60%, rgba(58,95,75,0.1) 80%, transparent 95%);
  border-radius: 2px;
}

.kpi-ink__label {
  font-size: 0.6875rem;
  color: #999;
  letter-spacing: 0.15em;
  margin-bottom: 6px;
}

.kpi-ink__big {
  font-size: 2.75rem;
  line-height: 1;
  color: #1a1a1a;
  font-family: 'Noto Serif SC', serif;
  font-weight: 700;
}

.kpi-ink__val {
  font-size: 1.5rem;
  line-height: 1;
  color: #333;
  font-family: 'Noto Serif SC', serif;
  font-weight: 700;
}

.kpi-ink__unit {
  font-size: 0.75rem;
  color: #999;
  font-weight: 300;
  margin-left: 3px;
}

.kpi-ink__hint {
  margin-top: 8px;
  font-size: 0.625rem;
  color: #bbb;
}

.kpi-ink__bar {
  height: 3px;
  border-radius: 2px;
  background: rgba(0,0,0,0.04);
  margin-top: 10px;
  overflow: hidden;
}

.kpi-ink__bar-f {
  height: 100%;
  border-radius: 2px;
  background: #3A5F4B;
  transition: width 1.2s cubic-bezier(.25,.46,.45,.94);
}

/* ===== 水墨卡片 ===== */
.ink-card {
  position: relative;
  padding: 22px;
  background: rgba(255,255,255,0.55);
  border: 1px solid rgba(0,0,0,0.04);
  border-radius: 12px;
  backdrop-filter: blur(8px);
  transition: all .3s;
}

.ink-card:hover {
  background: rgba(255,255,255,0.75);
  box-shadow: 0 8px 32px rgba(0,0,0,0.04);
}

.ink-card--wide { margin-top: 18px; }

.ink-card__hd {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
}

.ink-card__title {
  font-family: 'Ma Shan Zheng', cursive;
  font-size: 1.25rem;
  color: #333;
  letter-spacing: 0.1em;
}

/* 小印章 */
.ink-stamp {
  width: 28px; height: 28px;
  border-radius: 4px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-family: 'ZCOOL KuaiLe', cursive;
  font-size: 0.75rem;
  transform: rotate(-5deg);
}
.ink-stamp--green { border: 2px solid #3A5F4B; color: #3A5F4B; opacity: 0.5; }
.ink-stamp--teal  { border: 2px solid #2E8B57; color: #2E8B57; opacity: 0.5; }
.ink-stamp--purple { border: 2px solid #5B4B8C; color: #5B4B8C; opacity: 0.5; }
.ink-stamp--gold  { border: 2px solid #B8860B; color: #B8860B; opacity: 0.5; }

.ink-period-sm {
  font-size: 0.6875rem;
  padding: 2px 10px;
  border-radius: 4px;
  letter-spacing: 0.1em;
}

/* ===== 布局 ===== */
.tri-grid { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 14px; }
.duo-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; margin-top: 18px; }

/* ===== 仪表底部 ===== */
.gauge-bottom {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0;
  padding: 12px 0 0;
  border-top: 1px solid rgba(0,0,0,0.04);
  text-align: center;
}
.gauge-bottom > div { flex: 1; }
.gauge-bottom__l { font-size: 0.625rem; color: #bbb; margin-bottom: 2px; }
.gauge-bottom__v { font-size: 0.9375rem; color: #3A5F4B; }
.gauge-bottom__sep { width: 1px; height: 28px; background: rgba(0,0,0,0.04); }

/* ===== 碳排放 ===== */
.carbon-row { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-bottom: 12px; }
.carbon-item { text-align: center; padding: 16px 8px; background: rgba(58,95,75,0.03); border-radius: 8px; }
.carbon-item__l { font-size: 0.6875rem; color: #999; margin-top: 6px; }
.carbon-meta { display: flex; justify-content: space-between; font-size: 0.625rem; color: #bbb; padding-top: 10px; border-top: 1px solid rgba(0,0,0,0.04); }

/* ===== 图例 ===== */
.pie-legend { display:flex; flex-direction:column; gap:5px; margin-top:4px; }
.pie-legend__i { display:flex; align-items:center; gap:8px; font-size:.75rem; }
.pie-legend__dot { width:8px; height:8px; border-radius:2px; flex-shrink:0; }
.pie-legend__name { color:#666; flex:1; }
.pie-legend__pct { font-size:.8125rem; }

.trend-legend { display:flex; gap:14px; }
.trend-legend__i { display:flex; align-items:center; gap:5px; font-size:.6875rem; color:#999; }
.trend-legend__bar { width:16px; height:3px; border-radius:2px; opacity:.6; }

/* ===== 优化按钮（印章风） ===== */
.seal-btn {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 24px 10px 12px;
  border: none;
  background: transparent;
  cursor: pointer;
  transition: all .3s;
}

.seal-btn:hover:not(:disabled) { transform: translateY(-1px); }
.seal-btn:disabled { opacity: .6; cursor: not-allowed; }

.seal-btn__stamp {
  width: 36px; height: 36px;
  border: 2.5px solid #C41E3A;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-family: 'ZCOOL KuaiLe', cursive;
  font-size: 1rem;
  color: #C41E3A;
  transition: all .3s;
}

.seal-btn:hover:not(:disabled) .seal-btn__stamp {
  background: #C41E3A;
  color: white;
  box-shadow: 0 4px 16px rgba(196,30,58,0.2);
}

.seal-btn__text {
  font-family: 'ZCOOL XiaoWei', serif;
  font-size: 0.9375rem;
  color: #333;
  letter-spacing: 0.1em;
}

/* ===== 空态 ===== */
.opt-empty-ink {
  text-align: center;
  padding: 50px 20px 40px;
}

.opt-empty-ink__char {
  font-family: 'Ma Shan Zheng', cursive;
  font-size: 5rem;
  color: rgba(58,95,75,0.06);
  line-height: 1;
  margin-bottom: 12px;
}

.opt-empty-ink__t {
  font-family: 'Ma Shan Zheng', cursive;
  font-size: 1.25rem;
  color: #666;
  letter-spacing: 0.2em;
  margin-bottom: 8px;
}

.opt-empty-ink__d {
  font-size: 0.8125rem;
  color: #bbb;
  line-height: 1.8;
}

/* ===== 优化结果 ===== */
.opt-compare {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 32px;
  padding: 28px;
  background: rgba(58,95,75,0.02);
  border-radius: 12px;
  border: 1px solid rgba(0,0,0,0.03);
}

.opt-compare__item { text-align: center; }
.opt-compare__label { font-size: 0.6875rem; color: #999; margin-bottom: 8px; letter-spacing: 0.15em; }
.opt-compare__val { font-size: 1.75rem; line-height: 1; font-family: 'Noto Serif SC', serif; font-weight: 700; }
.opt-compare__u { font-size: 0.75rem; color: #999; font-weight: 300; }
.opt-compare__arrow { flex-shrink: 0; opacity: .4; animation: arrow-breathe 2.5s ease-in-out infinite; }
@keyframes arrow-breathe { 0%,100%{opacity:.3} 50%{opacity:.7} }
.opt-compare__sep { width: 1px; height: 50px; background: rgba(0,0,0,0.04); }
.opt-compare__meta { font-size: 0.6875rem; color: #bbb; margin-top: 6px; }

/* ===== 建议卡片 ===== */
.sug-grid-ink { display: grid; grid-template-columns: repeat(auto-fill, minmax(340px, 1fr)); gap: 12px; }

.sug-ink {
  display: flex;
  gap: 14px;
  padding: 18px;
  background: rgba(255,255,255,0.4);
  border: 1px solid rgba(0,0,0,0.03);
  border-radius: 10px;
  transition: all .25s;
}
.sug-ink:hover { background: rgba(255,255,255,0.7); box-shadow: 0 4px 16px rgba(0,0,0,0.03); }

.sug-ink__seal {
  width: 34px; height: 34px; flex-shrink: 0;
  border: 2px solid rgba(58,95,75,0.3);
  border-radius: 4px;
  display: flex; align-items: center; justify-content: center;
  font-family: 'ZCOOL KuaiLe', cursive;
  font-size: 0.8rem;
  color: #3A5F4B;
  transform: rotate(-3deg);
}

.sug-ink__body { flex: 1; min-width: 0; }
.sug-ink__top { display: flex; align-items: center; gap: 6px; margin-bottom: 8px; flex-wrap: wrap; }
.sug-ink__tag { font-size: 0.6875rem; font-weight: 500; color: #3A5F4B; background: rgba(58,95,75,0.06); padding: 2px 8px; border-radius: 3px; }
.sug-ink__gpu { font-size: 0.6875rem; font-weight: 500; color: #5B4B8C; background: rgba(91,75,140,0.06); padding: 2px 8px; border-radius: 3px; font-family: 'JetBrains Mono', monospace; }
.sug-ink__tgt { font-size: 0.6875rem; color: #999; font-family: 'JetBrains Mono', monospace; }
.sug-ink__save { margin-left: auto; font-size: 0.8125rem; font-weight: 700; color: #2E8B57; font-family: 'JetBrains Mono', monospace; }
.sug-ink__reason { font-size: 0.8125rem; color: #666; line-height: 1.65; }

/* ===== 导出按钮（小号印章风） ===== */
.seal-btn--sm { padding: 4px 12px 4px 6px; gap: 6px; }
.seal-btn__stamp--sm { width: 26px; height: 26px; font-size: 0.75rem; border-width: 2px; }
.seal-btn__text--sm { font-size: 0.75rem; }

/* ===== 对比图累计节省标签 ===== */
.comp-saved {
  font-size: 0.75rem;
  color: #2E8B57;
  background: rgba(46,139,87,0.06);
  padding: 2px 10px;
  border-radius: 4px;
  margin-left: 8px;
}

/* ===== 调度时间线 ===== */
.schedule-timeline { padding: 0 4px; }
.sched-stats {
  display: flex;
  gap: 16px;
  font-size: 0.75rem;
  color: #999;
  margin-bottom: 16px;
  padding-bottom: 12px;
  border-bottom: 1px solid rgba(0,0,0,0.04);
}
.sched-stats b { font-family: 'Noto Serif SC', serif; }

.timeline-list { position: relative; padding-left: 20px; }

.timeline-item {
  position: relative;
  padding-bottom: 16px;
}
.timeline-item:last-child .timeline-line { display: none; }

.timeline-dot {
  position: absolute;
  left: -20px;
  top: 6px;
  width: 10px; height: 10px;
  border-radius: 50%;
  background: #3A5F4B;
  border: 2px solid rgba(58,95,75,0.2);
  z-index: 1;
}
.timeline-dot--fail { background: #C41E3A; border-color: rgba(196,30,58,0.2); }

.timeline-line {
  position: absolute;
  left: -16px;
  top: 18px;
  bottom: 0;
  width: 2px;
  background: rgba(0,0,0,0.04);
}

.timeline-card {
  padding: 12px 16px;
  background: rgba(255,255,255,0.4);
  border: 1px solid rgba(0,0,0,0.03);
  border-radius: 8px;
  transition: all .25s;
}
.timeline-card:hover { background: rgba(255,255,255,0.7); box-shadow: 0 4px 16px rgba(0,0,0,0.03); }

.timeline-card__top {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  margin-bottom: 6px;
}

.timeline-card__time {
  font-size: 0.6875rem;
  color: #999;
  font-family: 'JetBrains Mono', monospace;
}

.timeline-card__action {
  font-size: 0.6875rem;
  font-weight: 500;
  color: #3A5F4B;
  background: rgba(58,95,75,0.06);
  padding: 1px 8px;
  border-radius: 3px;
}
.timeline-card__action--ai { color: #5B4B8C; background: rgba(91,75,140,0.08); }

.timeline-card__target {
  font-size: 0.6875rem;
  color: #5B4B8C;
  font-family: 'JetBrains Mono', monospace;
  background: rgba(91,75,140,0.06);
  padding: 1px 8px;
  border-radius: 3px;
}

.timeline-card__result {
  margin-left: auto;
  font-size: 0.625rem;
  color: #2E8B57;
  font-weight: 500;
}
.timeline-card__result--fail { color: #C41E3A; }
.timeline-card__result--neutral { color: #5B4B8C; }

.timeline-card__reason {
  font-size: 0.8125rem;
  color: #666;
  line-height: 1.6;
}

/* ===== 底部装饰 ===== */
.ink-footer {
  display: flex;
  justify-content: center;
  padding: 32px 0 16px;
}

.ink-vert-text {
  writing-mode: vertical-rl;
  text-orientation: mixed;
  font-family: 'Ma Shan Zheng', cursive;
  font-size: 0.875rem;
  color: rgba(0,0,0,0.08);
  letter-spacing: 0.5em;
  height: 180px;
}

/* ===== Loading ===== */
.ink-loading {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 120px 20px;
}

.ink-loading__brush {
  width: 40px; height: 3px;
  background: linear-gradient(90deg, transparent, #3A5F4B, transparent);
  border-radius: 2px;
  animation: brush-stroke 1.5s ease-in-out infinite;
}

@keyframes brush-stroke {
  0% { transform: scaleX(0.3); opacity: 0.3; }
  50% { transform: scaleX(1); opacity: 1; }
  100% { transform: scaleX(0.3); opacity: 0.3; }
}

.ink-loading__text {
  font-family: 'ZCOOL XiaoWei', serif;
  color: #999;
  margin-top: 20px;
  font-size: 0.875rem;
  letter-spacing: 0.2em;
}

/* ===== AI 能力区块样式 ===== */
.ink-card--ai {
  background: linear-gradient(135deg, rgba(91,75,140,0.03), rgba(255,255,255,0.55));
  border-color: rgba(91,75,140,0.08);
}
.ink-stamp--ai { border: 2px solid #5B4B8C; color: #5B4B8C; opacity: 0.5; }

.ai-risk-badge {
  font-size: 0.625rem;
  padding: 2px 10px;
  border-radius: 4px;
  letter-spacing: 0.05em;
  margin-left: auto;
}
.ai-risk-badge--low { color: #2E8B57; background: rgba(46,139,87,0.08); }
.ai-risk-badge--medium { color: #B8860B; background: rgba(184,134,11,0.08); }
.ai-risk-badge--high { color: #C41E3A; background: rgba(196,30,58,0.08); }

/* D2: AI洞察 */
.ai-insight-body { padding: 0 4px; }
.ai-insight-summary {
  font-family: 'Ma Shan Zheng', cursive;
  font-size: 1.15rem;
  color: #333;
  letter-spacing: 0.05em;
  margin-bottom: 8px;
}
.ai-insight-detail {
  font-size: 0.8125rem;
  color: #666;
  line-height: 1.7;
  margin-bottom: 12px;
}
.ai-insight-suggestions { display: flex; flex-wrap: wrap; gap: 8px; }
.ai-insight-sug {
  font-size: 0.75rem;
  color: #5B4B8C;
  background: rgba(91,75,140,0.06);
  padding: 4px 12px;
  border-radius: 4px;
  border-left: 2px solid rgba(91,75,140,0.3);
}

/* D3: AI预测解读 */
.ai-interpret-box {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  margin-top: 14px;
  padding: 12px 16px;
  background: rgba(91,75,140,0.04);
  border-left: 3px solid rgba(91,75,140,0.3);
  border-radius: 0 8px 8px 0;
}
.ai-interpret-icon {
  flex-shrink: 0;
  width: 22px; height: 22px;
  border: 1.5px solid #5B4B8C;
  border-radius: 3px;
  display: flex; align-items: center; justify-content: center;
  font-family: 'ZCOOL KuaiLe', cursive;
  font-size: 0.625rem;
  color: #5B4B8C;
  opacity: 0.6;
}
.ai-interpret-text {
  font-size: 0.8125rem;
  color: #666;
  line-height: 1.7;
}

/* D1: AI异常检测 */
.ai-anomaly-list { display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap: 10px; }
.ai-anomaly-item {
  padding: 14px 16px;
  background: rgba(255,255,255,0.4);
  border: 1px solid rgba(0,0,0,0.03);
  border-radius: 8px;
  border-left: 3px solid #B8860B;
}
.ai-anomaly-item--critical { border-left-color: #C41E3A; }
.ai-anomaly-item__head { display: flex; align-items: center; gap: 8px; margin-bottom: 6px; }
.ai-anomaly-item__type { font-size: 0.8125rem; font-weight: 500; color: #333; }
.ai-anomaly-item__gpu { font-size: 0.6875rem; color: #5B4B8C; background: rgba(91,75,140,0.06); padding: 1px 8px; border-radius: 3px; font-family: 'JetBrains Mono', monospace; }
.ai-anomaly-item__sev { margin-left: auto; font-size: 0.625rem; font-weight: 500; padding: 1px 8px; border-radius: 3px; }
.ai-anomaly-item__sev--warning { color: #B8860B; background: rgba(184,134,11,0.08); }
.ai-anomaly-item__sev--critical { color: #C41E3A; background: rgba(196,30,58,0.08); }
.ai-anomaly-item__desc { font-size: 0.8125rem; color: #666; line-height: 1.6; }
.ai-anomaly-item__sug { font-size: 0.75rem; color: #5B4B8C; margin-top: 6px; padding-top: 6px; border-top: 1px solid rgba(0,0,0,0.04); }

/* D4: AI调度评估（内联） */
.ai-eval-inline {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 6px;
  padding-top: 6px;
  border-top: 1px dashed rgba(91,75,140,0.15);
}
.ai-eval-inline__score {
  font-family: 'Noto Serif SC', serif;
  font-weight: 700;
  font-size: 0.875rem;
}
.ai-eval-inline__verdict {
  font-size: 0.75rem;
  color: #666;
}

/* ===== 卡片标题组（eyebrow + title） ===== */
.ink-card__title-group {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.ink-card__eyebrow {
  font-size: 0.625rem;
  color: #999;
  letter-spacing: 0.12em;
  font-family: 'ZCOOL XiaoWei', serif;
}

/* ===== AI 加载态 ===== */
.ai-loading-box {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 36px 20px;
}
.ai-loading-box__brush {
  width: 36px; height: 3px;
  background: linear-gradient(90deg, transparent, #5B4B8C, transparent);
  border-radius: 2px;
  animation: brush-stroke 1.5s ease-in-out infinite;
}
.ai-loading-box__text {
  margin-top: 14px;
  font-size: 0.8125rem;
  color: #999;
  letter-spacing: 0.15em;
}

/* ===== AI 健康态 ===== */
.ai-healthy-box {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 32px 20px 28px;
}
.ai-healthy-box__icon {
  width: 48px; height: 48px;
  border: 2.5px solid #2E8B57;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-family: 'ZCOOL KuaiLe', cursive;
  font-size: 1.25rem;
  color: #2E8B57;
  opacity: 0.7;
  margin-bottom: 14px;
}
.ai-healthy-box__text {
  font-family: 'Ma Shan Zheng', cursive;
  font-size: 1.1rem;
  color: #2E8B57;
  letter-spacing: 0.08em;
  margin-bottom: 6px;
}
.ai-healthy-box__sub {
  font-size: 0.75rem;
  color: #999;
  text-align: center;
  line-height: 1.7;
  max-width: 480px;
}

/* ===== AI 空态/LLM未接入提示 ===== */
.ai-empty-hint {
  font-size: 0.8125rem;
  color: #999;
  padding: 20px 4px;
  text-align: center;
}
.ai-empty-hint--llm {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 32px 20px 28px;
}
.ai-empty-hint__icon {
  width: 48px; height: 48px;
  border: 2.5px dashed rgba(91,75,140,0.35);
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-family: 'ZCOOL KuaiLe', cursive;
  font-size: 1.25rem;
  color: #5B4B8C;
  opacity: 0.5;
  margin-bottom: 14px;
}
.ai-empty-hint__text {
  font-family: 'Ma Shan Zheng', cursive;
  font-size: 1.1rem;
  color: #5B4B8C;
  letter-spacing: 0.08em;
  margin-bottom: 6px;
}
.ai-empty-hint__sub {
  font-size: 0.75rem;
  color: #999;
  text-align: center;
  line-height: 1.7;
  max-width: 520px;
}

/* ===== 响应式 ===== */
@media(max-width:1400px){
  .source-strip{grid-template-columns:1fr}
  .kpi-grid{grid-template-columns:repeat(3,1fr)}
  .kpi-ink--hero{grid-column:span 3;flex-direction:row;gap:20px}
  .tri-grid,.duo-grid{grid-template-columns:1fr}
}
@media(max-width:900px){
  .ink-header{align-items:flex-start;flex-direction:column;gap:12px}
  .ink-header__right{justify-content:flex-start}
  .kpi-grid{grid-template-columns:repeat(2,1fr)}
  .kpi-ink--hero{grid-column:span 2}
  .sug-grid-ink{grid-template-columns:1fr}
  .opt-compare{flex-wrap:wrap;gap:16px}
  .ink-seal{display:none}
}
</style>
