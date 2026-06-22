(function() {
  var style = getComputedStyle(document.documentElement);
  var accent = style.getPropertyValue('--accent').trim();
  var accent2 = style.getPropertyValue('--accent2').trim();
  var accent3 = style.getPropertyValue('--accent3').trim();
  var ink = style.getPropertyValue('--ink').trim();
  var muted = style.getPropertyValue('--muted').trim();
  var rule = style.getPropertyValue('--rule').trim();
  var bg2 = style.getPropertyValue('--bg2').trim();
  var warn = style.getPropertyValue('--warn').trim();

  // --- Chart 1: Issue Distribution by Dimension ---
  var chart1 = echarts.init(document.getElementById('chart-issues'), null, { renderer: 'svg' });
  chart1.setOption({
    animation: false,
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
      appendToBody: true,
      textStyle: { fontSize: 12 }
    },
    legend: {
      data: ['严重', '警告', '改进'],
      top: 0,
      right: 10,
      textStyle: { color: muted, fontSize: 12 }
    },
    grid: { left: 80, right: 30, top: 40, bottom: 30 },
    xAxis: {
      type: 'value',
      axisLine: { lineStyle: { color: rule } },
      axisLabel: { color: muted, fontSize: 12 },
      splitLine: { lineStyle: { color: rule, type: 'dashed' } }
    },
    yAxis: {
      type: 'category',
      data: ['前端体验', '数据库/Schema', 'AI 模块', '安全/健壮性', '架构设计', '任务管理', '性能'],
      axisLine: { lineStyle: { color: rule } },
      axisLabel: { color: ink, fontSize: 12 }
    },
    series: [
      {
        name: '严重',
        type: 'bar',
        stack: 'total',
        itemStyle: { color: accent2 },
        barWidth: 22,
        data: [0, 1, 2, 4, 2, 1, 2]
      },
      {
        name: '警告',
        type: 'bar',
        stack: 'total',
        itemStyle: { color: warn },
        data: [2, 2, 2, 2, 3, 2, 2]
      },
      {
        name: '改进',
        type: 'bar',
        stack: 'total',
        itemStyle: { color: accent },
        data: [3, 2, 1, 1, 2, 1, 2]
      }
    ]
  });
  window.addEventListener('resize', function() { chart1.resize(); });

  // --- Chart 2: Priority Matrix ---
  var chart2 = echarts.init(document.getElementById('chart-priority'), null, { renderer: 'svg' });
  chart2.setOption({
    animation: false,
    tooltip: {
      appendToBody: true,
      textStyle: { fontSize: 12 },
      formatter: function(p) {
        return '<b>' + p.data[3] + '</b><br/>影响范围: ' + p.data[0] + '<br/>实施难度: ' + p.data[1] + '<br/>优先级: ' + p.data[2];
      }
    },
    grid: { left: 60, right: 30, top: 30, bottom: 50 },
    xAxis: {
      type: 'value',
      name: '影响范围 →',
      nameLocation: 'middle',
      nameGap: 30,
      nameTextStyle: { color: muted, fontSize: 12 },
      min: 0, max: 10,
      axisLine: { lineStyle: { color: rule } },
      axisLabel: { color: muted, fontSize: 11 },
      splitLine: { lineStyle: { color: rule, type: 'dashed' } }
    },
    yAxis: {
      type: 'value',
      name: '实施难度 ↑',
      nameLocation: 'middle',
      nameGap: 40,
      nameTextStyle: { color: muted, fontSize: 12 },
      min: 0, max: 10,
      axisLine: { lineStyle: { color: rule } },
      axisLabel: { color: muted, fontSize: 11 },
      splitLine: { lineStyle: { color: rule, type: 'dashed' } }
    },
    series: [
      {
        type: 'scatter',
        symbolSize: function(data) { return data[2] * 8; },
        data: [
          [9.5, 3, 5, 'API 认证授权'],
          [9, 2.5, 5, '文件上传大小限制'],
          [8.5, 2, 5, '恢复 PIL 解压炸弹保护'],
          [8, 2, 5, '修复 _parse_json Bug'],
          [7.5, 1.5, 5, '修复 or 短路 Bug'],
          [9, 7, 4, '迁移 Celery 任务队列'],
          [8, 5, 4, '拆分 task_service 上帝类'],
          [7.5, 4, 4, 'AI 调用并发化'],
          [8.5, 3.5, 4, '消除 N+1 查询'],
          [7, 6, 3, '状态机抽取为 Enum'],
          [6, 5, 3, '引入结构化日志'],
          [6.5, 4, 3, '前端 React Query 数据层'],
          [5, 3, 2, '文件 hash 去重'],
          [4.5, 2.5, 2, '补齐 404 + ErrorBoundary'],
          [4, 3, 2, '移动端导航适配'],
          [5.5, 4, 2, 'Excel 流式导出 + CJK 列宽'],
          [4, 5, 2, 'Provider 异常层级'],
          [3.5, 3, 2, 'models 按领域拆分']
        ],
        itemStyle: {
          color: function(p) {
            var priority = p.data[2];
            if (priority >= 5) return accent2;
            if (priority >= 4) return warn;
            if (priority >= 3) return accent;
            return accent3;
          },
          opacity: 0.85,
          borderColor: bg2,
          borderWidth: 2
        },
        label: {
          show: true,
          position: 'right',
          formatter: function(p) { return p.data[3]; },
          fontSize: 10,
          color: ink
        }
      }
    ],
    visualMap: {
      show: false,
      dimension: 2,
      min: 2, max: 5,
      inRange: { color: [accent3, accent, warn, accent2] }
    }
  });
  window.addEventListener('resize', function() { chart2.resize(); });
})();
