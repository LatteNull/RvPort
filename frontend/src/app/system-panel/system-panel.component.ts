import { Component } from '@angular/core';
import { PlxMessage } from 'paletx';
import * as echarts from 'echarts';
import { DashboardApi } from '../api/dashboard-api.service';
import { PluginManagerApi } from '../api/plugin-manager-api.service';

@Component({
  selector: 'app-system-panel',
  templateUrl: './system-panel.component.html',
  styleUrl: './system-panel.component.css',
  standalone: false,
})

export class SystemPanelComponent {

  /** 插件安装状态：codemig 是否已安装 */
  codemigInstalled = false;
  /** 插件列表加载完成（失败时按可用兜底，不阻塞面板） */
  pluginKnown = false;
  /** codemig 未安装：整页显示空态提示 */
  noPluginAvailable = false;

  online_user_count: number = 0;
  task_count: number = 0;
  issue_count: number = 0;
  ai_usage: number = 0;

  sequenceOptions: any;
  sequenceData: any;
  loading: boolean = false;

  startDate: Date | string | null = null;
  endDate: Date | string | null = null;
  minDate: Date | string | null = null;
  maxDate: Date | string | null = null;

  userTasksData: any;
  userTasksPieOptions: any;

  secondaryPieData: any;
  secondaryPieOptions: any;

  constructor(
    private plxMessage: PlxMessage,
    private dashboardApi: DashboardApi,
    private pluginManagerApi: PluginManagerApi,
  ) {}

  ngOnInit(): void {
    // 给日期选择器一个稳定的可选范围，避免刷新后把 minDate 锁死到当前区间起点
    if (!this.maxDate) this.maxDate = new Date();
    if (!this.minDate) this.minDate = new Date('2000-01-01');
    this.loadPluginStatus();
  }

  /** 拉取插件安装状态，codemig 未装则显示空态 */
  private loadPluginStatus(): void {
    this.pluginManagerApi.getPluginList().subscribe({
      next: (res: any) => {
        if (res?.code === 0 && Array.isArray(res.data)) {
          for (const item of res.data) {
            if (item?.type === 'codemig') this.codemigInstalled = item.isOK === 'OK';
          }
          this.pluginKnown = true;
        }
        this.applyPluginGate();
      },
      error: () => {
        // 插件接口异常时按可用兜底，不阻塞面板
        this.pluginKnown = false;
        this.applyPluginGate();
      },
    });
  }

  /** 根据插件安装状态收敛空态标记 */
  private applyPluginGate(): void {
    if (this.pluginKnown && !this.codemigInstalled) {
      this.noPluginAvailable = true;
      return;
    }
    this.noPluginAvailable = false;
    this.refreshData();
  }

  private formatDate(d: Date | string | null): string | undefined {
    if (!d) return undefined;
    const dt = d instanceof Date ? d : new Date(d);
    if (Number.isNaN(dt.getTime())) return undefined;
    const yyyy = dt.getFullYear();
    const mm = String(dt.getMonth() + 1).padStart(2, '0');
    const dd = String(dt.getDate()).padStart(2, '0');
    return `${yyyy}-${mm}-${dd}`;
  }

  buildUserTasksPieOptions() {
    return {
      title: { text: '用户任务分布占比', left: 'center' },
      tooltip: { trigger: 'item', formatter: '{a} <br/>{b}: {c} ({d}%)' },
      legend: { bottom: '0', left: 'center', type: 'scroll' },
      series: [{
        name: '任务量占比',
        type: 'pie',
        radius: '60%',
        data: this.userTasksData || [],
        emphasis: {
          itemStyle: {
            shadowBlur: 10,
            shadowOffsetX: 0,
            shadowColor: 'rgba(0, 0, 0, 0.5)'
          }
        }
      }]
    };
  }

  buildSecondaryPieOptions() {
    return {
      title: { text: '问题类型分布', left: 'center' },
      tooltip: { trigger: 'item', formatter: '{a} <br/>{b}: {c} ({d}%)' },
      legend: { bottom: '0', left: 'center', type: 'scroll' },
      series: [{
        name: '问题占比',
        type: 'pie',
        radius: '60%',
        data: this.secondaryPieData || [],
        emphasis: {
          itemStyle: {
            shadowBlur: 10,
            shadowOffsetX: 0,
            shadowColor: 'rgba(0, 0, 0, 0.5)'
          }
        }
      }]
    };
  }

  buildMigrationSequenceOptions() {
    return {
      tooltip: {
        trigger: 'axis',
        backgroundColor: 'rgba(255, 255, 255, 0.95)',
        boxShadow: '0 4px 12px rgba(0,0,0,0.1)',
        padding: 12,
        textStyle: { color: '#333' },
        borderWidth: 0,
        axisPointer: {
          type: 'cross',
          label: { backgroundColor: '#6a7985' }
        }
      },
      legend: {
        data: ['登录用户', '迁移任务', '问题数量', 'AI使用次数'],
        top: 0,
        icon: 'circle',
        itemGap: 20
      },
      grid: {
        left: '2%',
        right: '2%',
        bottom: '10%',
        top: '12%',
        containLabel: true
      },
      xAxis: [{
        type: 'category',
        boundaryGap: true,
        data: this.sequenceData?.time_stamp || [],
        axisLine: { lineStyle: { color: '#e2e8f0' } },
        axisLabel: {
          color: '#64748b',
          formatter: (value: string) => value.slice(5)
        }
      }],
      yAxis: [
        {
          type: 'value',
          name: '业务量级',
          position: 'left',
          nameTextStyle: { color: '#64748b', padding: [0, 0, 0, -20] },
          axisLine: { show: true },
          axisTick: { show: true },
          axisLabel: { color: '#64748b' },
          splitLine: { lineStyle: { type: 'dashed', color: '#f1f5f9' } }
        },
        {
          type: 'value',
          name: '问题数',
          position: 'right',
          nameTextStyle: { color: '#ef4444', padding: [0, -20, 0, 0] },
          axisLine: { show: true },
          axisTick: { show: true },
          axisLabel: { color: '#ef4444' },
          splitLine: { show: false }
        }
      ],
      dataZoom: [
        {
          type: 'slider',
          show: true,
          height: 20,
          bottom: 0,
          borderColor: 'transparent',
          backgroundColor: '#f1f5f9',
          fillerColor: 'rgba(52, 152, 219, 0.2)',
          handleStyle: { color: '#3498db', shadowBlur: 3 },
          start: 0,
          end: 100
        },
        { type: 'inside', start: 0, end: 100 }
      ],
      series: [
        {
          name: '登录用户',
          type: 'line',
          smooth: true,
          symbol: 'none',
          lineStyle: { width: 3, color: '#3498db' },
          areaStyle: {
            color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
              { offset: 0, color: 'rgba(52, 152, 219, 0.4)' },
              { offset: 1, color: 'rgba(52, 152, 219, 0.05)' }
            ])
          },
          data: this.sequenceData?.user_count || []
        },
        {
          name: '迁移任务',
          type: 'line',
          smooth: true,
          symbol: 'none',
          lineStyle: { width: 3, color: '#8b5cf6' },
          itemStyle: { color: '#8b5cf6' },
          data: this.sequenceData?.task_count || []
        },
        {
          name: 'AI使用次数',
          type: 'line',
          smooth: true,
          symbol: 'none',
          lineStyle: { width: 3, color: '#f59e0b' },
          itemStyle: { color: '#f59e0b' },
          data: this.sequenceData?.ai_usage || []
        },
        {
          name: '问题数量',
          type: 'bar',
          yAxisIndex: 1,
          barMaxWidth: 15,
          itemStyle: {
            color: '#ef4444',
            borderRadius: [4, 4, 0, 0]
          },
          data: this.sequenceData?.issue_count || []
        }
      ]
    };
  }

  refreshData() {
    if (this.loading) return;
    this.loading = true;
    const start = this.formatDate(this.startDate);
    const end = this.formatDate(this.endDate);
    this.dashboardApi.getSystemPanel({ start, end }).subscribe({
      next: (resp: any) => {
        if (resp?.code === 0) {
          const data = resp?.data || {};
          const summary = data.summary || {};
          const ts = data.timeseries || {};

          this.online_user_count = Number(summary.online_user_count || 0);
          this.task_count = Number(summary.task_count || 0);
          this.issue_count = Number(summary.issue_count ?? 0);
          this.ai_usage = Number(summary.ai_usage || 0);

          this.sequenceData = {
            time_stamp: ts.time_stamp || [],
            user_count: ts.user_count || [],
            task_count: ts.task_count || [],
            issue_count: ts.issue_count || [],
            ai_usage: ts.ai_usage || [],
          };

          // 不覆盖 minDate/maxDate（否则会导致无法往前选日期）
          // 仅在首次加载时填充默认 start/end
          if (!this.startDate && ts.start) this.startDate = new Date(ts.start);
          if (!this.endDate && ts.end) this.endDate = new Date(ts.end);

          this.userTasksData = data.user_task_pie || [];
          this.secondaryPieData = data.issue_type_pie || [];

          this.sequenceOptions = this.buildMigrationSequenceOptions();
          this.userTasksPieOptions = this.buildUserTasksPieOptions();
          this.secondaryPieOptions = this.buildSecondaryPieOptions();

          this.plxMessage.show('success', { title: '刷新成功', isLightweight: true });
        } else {
          this.plxMessage.show('warning', { title: '刷新失败', content: resp?.msg || '接口返回异常', isLightweight: true });
        }
        this.loading = false;
      },
      error: () => {
        this.loading = false;
        this.plxMessage.show('warning', { title: '刷新失败', content: '网络或服务异常', isLightweight: true });
      }
    });
  }

  onStartDateChange(event: any): void {
    let selectedDate: Date;
    if (event instanceof Date) {
      selectedDate = event;
    } else if (event && event.date) {
      selectedDate = event.date instanceof Date ? event.date : new Date(event.date);
    } else if (event) {
      selectedDate = new Date(event);
    } else {
      return;
    }
    if (this.endDate && selectedDate > this.endDate) {
      this.plxMessage.show('warning', {
        title: '提示',
        content: '开始日期不能晚于结束日期',
        isLightweight: true
      });
      return;
    }
    if (this.minDate && selectedDate < this.minDate) {
      this.startDate = new Date(this.minDate);
      this.plxMessage.show('warning', {
        title: '提示',
        content: '开始日期不能早于最早可选日期',
        isLightweight: true
      });
      this.refreshData();
      return;
    }
    this.startDate = selectedDate;
    this.refreshData();
  }

  onEndDateChange(event: any): void {
    let selectedDate: Date;
    if (event instanceof Date) {
      selectedDate = event;
    } else if (event && event.date) {
      selectedDate = event.date instanceof Date ? event.date : new Date(event.date);
    } else if (event) {
      selectedDate = new Date(event);
    } else {
      return;
    }
    if (this.startDate && selectedDate < this.startDate) {
      this.plxMessage.show('warning', {
        title: '提示',
        content: '结束日期不能早于开始日期',
        isLightweight: true
      });
      return;
    }
    if (this.maxDate && selectedDate > this.maxDate) {
      this.endDate = new Date(this.maxDate);
      this.plxMessage.show('warning', {
        title: '提示',
        content: '结束日期不能晚于最晚可选日期',
        isLightweight: true
      });
      this.refreshData();
      return;
    }
    this.endDate = selectedDate;
    this.refreshData();
  }
}
