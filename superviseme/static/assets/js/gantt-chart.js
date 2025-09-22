/**
 * Simple Gantt Chart Implementation for SuperviseMe
 * Displays thesis timeline with updates, todos, feedback, and status changes
 */
class ThesisGanttChart {
    constructor(container, options = {}) {
        this.container = typeof container === 'string' ? document.getElementById(container) : container;
        this.options = {
            height: options.height || 400,
            barHeight: options.barHeight || 20,
            barSpacing: options.barSpacing || 5,
            marginLeft: options.marginLeft || 200,
            marginTop: options.marginTop || 50,
            marginBottom: options.marginBottom || 50,
            colors: {
                thesis_milestone: '#6f42c1',
                student_update: '#28a745',
                supervisor_feedback: '#007bff',
                todo_pending: '#ffc107',
                todo_completed: '#20c997',
                todo_cancelled: '#dc3545',
                status_change: '#17a2b8'
            },
            ...options
        };
        
        this.data = null;
        this.chart = null;
        this.init();
    }
    
    init() {
        this.container.innerHTML = '';
        this.container.style.position = 'relative';
        this.container.style.overflow = 'auto';
        
        // Create chart container
        this.chart = document.createElement('div');
        this.chart.style.position = 'relative';
        this.chart.style.width = '100%';
        this.chart.style.minWidth = '800px';
        this.chart.style.height = this.options.height + 'px';
        this.chart.style.backgroundColor = '#f8f9fa';
        this.chart.style.border = '1px solid #dee2e6';
        this.chart.style.borderRadius = '0.375rem';
        
        this.container.appendChild(this.chart);
    }
    
    async loadData(thesisId) {
        try {
            const response = await fetch(`/api/thesis/${thesisId}/gantt_data`);
            if (!response.ok) {
                throw new Error('Failed to load Gantt data');
            }
            this.data = await response.json();
            this.render();
        } catch (error) {
            console.error('Error loading Gantt data:', error);
            this.showError('Failed to load timeline data');
        }
    }
    
    render() {
        if (!this.data || !this.data.events || this.data.events.length === 0) {
            this.showError('No timeline data available');
            return;
        }
        
        this.chart.innerHTML = '';
        
        // Calculate time range
        const events = this.data.events;
        const startTime = Math.min(...events.map(e => e.start));
        const endTime = Math.max(...events.map(e => e.end));
        const timeRange = endTime - startTime;
        const chartWidth = this.chart.offsetWidth - this.options.marginLeft - 50;
        
        // Create header
        this.createHeader();
        
        // Create time axis
        this.createTimeAxis(startTime, endTime, timeRange, chartWidth);
        
        // Group events by category
        const categories = this.data.categories || ['All'];
        const eventsByCategory = this.groupEventsByCategory(events);
        
        let yOffset = this.options.marginTop + 40; // Account for time axis
        
        categories.forEach(category => {
            const categoryEvents = eventsByCategory[category] || [];
            if (categoryEvents.length === 0) return;
            
            // Category header
            const categoryHeader = this.createElement('div', {
                position: 'absolute',
                left: '10px',
                top: yOffset + 'px',
                width: (this.options.marginLeft - 20) + 'px',
                height: '25px',
                backgroundColor: '#e9ecef',
                border: '1px solid #ced4da',
                borderRadius: '3px',
                padding: '5px 10px',
                fontSize: '12px',
                fontWeight: 'bold',
                display: 'flex',
                alignItems: 'center'
            });
            categoryHeader.textContent = category;
            this.chart.appendChild(categoryHeader);
            
            yOffset += 30;
            
            // Render events in this category
            categoryEvents.forEach(event => {
                this.renderEvent(event, yOffset, startTime, timeRange, chartWidth);
                yOffset += this.options.barHeight + this.options.barSpacing;
            });
            
            yOffset += 10; // Space between categories
        });
        
        // Update chart height
        this.chart.style.height = Math.max(yOffset + this.options.marginBottom, this.options.height) + 'px';
    }
    
    createHeader() {
        const header = this.createElement('div', {
            position: 'absolute',
            left: '10px',
            top: '10px',
            fontSize: '16px',
            fontWeight: 'bold',
            color: '#495057'
        });
        header.textContent = `Timeline: ${this.data.thesis.title}`;
        this.chart.appendChild(header);
    }
    
    createTimeAxis(startTime, endTime, timeRange, chartWidth) {
        const axisY = this.options.marginTop;
        
        // Time axis line
        const axisLine = this.createElement('div', {
            position: 'absolute',
            left: this.options.marginLeft + 'px',
            top: axisY + 'px',
            width: chartWidth + 'px',
            height: '1px',
            backgroundColor: '#6c757d'
        });
        this.chart.appendChild(axisLine);
        
        // Time labels (show month/year markers)
        const numLabels = Math.min(6, Math.floor(chartWidth / 100));
        for (let i = 0; i <= numLabels; i++) {
            const timePoint = startTime + (timeRange * i / numLabels);
            const x = this.options.marginLeft + (chartWidth * i / numLabels);
            
            const tick = this.createElement('div', {
                position: 'absolute',
                left: (x - 1) + 'px',
                top: (axisY - 5) + 'px',
                width: '2px',
                height: '10px',
                backgroundColor: '#6c757d'
            });
            this.chart.appendChild(tick);
            
            const label = this.createElement('div', {
                position: 'absolute',
                left: (x - 40) + 'px',
                top: (axisY + 10) + 'px',
                width: '80px',
                textAlign: 'center',
                fontSize: '10px',
                color: '#6c757d'
            });
            label.textContent = new Date(timePoint).toLocaleDateString('en-US', { 
                month: 'short', 
                day: 'numeric',
                year: '2-digit'
            });
            this.chart.appendChild(label);
        }
    }
    
    renderEvent(event, yOffset, startTime, timeRange, chartWidth) {
        const duration = Math.max(event.end - event.start, 86400000); // Minimum 1 day width
        const x = this.options.marginLeft + ((event.start - startTime) / timeRange) * chartWidth;
        const width = Math.max((duration / timeRange) * chartWidth, 20); // Minimum width
        
        const color = this.options.colors[event.type] || '#6c757d';
        
        // Event bar
        const bar = this.createElement('div', {
            position: 'absolute',
            left: x + 'px',
            top: yOffset + 'px',
            width: width + 'px',
            height: this.options.barHeight + 'px',
            backgroundColor: color,
            border: '1px solid ' + this.darkenColor(color, 0.2),
            borderRadius: '3px',
            cursor: 'pointer',
            opacity: '0.8',
            transition: 'opacity 0.2s'
        });
        
        // Event label
        const label = this.createElement('div', {
            position: 'absolute',
            left: '10px',
            top: yOffset + 2 + 'px',
            width: (this.options.marginLeft - 20) + 'px',
            height: (this.options.barHeight - 4) + 'px',
            fontSize: '11px',
            color: '#495057',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap',
            display: 'flex',
            alignItems: 'center',
            paddingRight: '5px'
        });
        label.textContent = event.title;
        
        // Hover effects and tooltip
        bar.addEventListener('mouseenter', () => {
            bar.style.opacity = '1';
            this.showTooltip(event, bar);
        });
        
        bar.addEventListener('mouseleave', () => {
            bar.style.opacity = '0.8';
            this.hideTooltip();
        });
        
        this.chart.appendChild(bar);
        this.chart.appendChild(label);
    }
    
    showTooltip(event, element) {
        const tooltip = document.getElementById('gantt-tooltip') || this.createTooltip();
        
        const rect = element.getBoundingClientRect();
        const containerRect = this.container.getBoundingClientRect();
        
        tooltip.innerHTML = `
            <div style="font-weight: bold; margin-bottom: 5px;">${event.title}</div>
            <div style="margin-bottom: 3px;"><strong>Date:</strong> ${new Date(event.start).toLocaleDateString()}</div>
            ${event.author ? `<div style="margin-bottom: 3px;"><strong>Author:</strong> ${event.author}</div>` : ''}
            ${event.priority ? `<div style="margin-bottom: 3px;"><strong>Priority:</strong> ${event.priority}</div>` : ''}
            ${event.status ? `<div style="margin-bottom: 3px;"><strong>Status:</strong> ${event.status}</div>` : ''}
            ${event.assigned_to ? `<div style="margin-bottom: 3px;"><strong>Assigned to:</strong> ${event.assigned_to}</div>` : ''}
            <div style="margin-top: 5px; font-size: 12px; color: #6c757d;">${event.description}</div>
        `;
        
        tooltip.style.left = (rect.left - containerRect.left + rect.width + 10) + 'px';
        tooltip.style.top = (rect.top - containerRect.top) + 'px';
        tooltip.style.display = 'block';
    }
    
    createTooltip() {
        const tooltip = document.createElement('div');
        tooltip.id = 'gantt-tooltip';
        tooltip.style.cssText = `
            position: absolute;
            background: #fff;
            border: 1px solid #ccc;
            border-radius: 4px;
            padding: 10px;
            max-width: 300px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            z-index: 1000;
            font-size: 12px;
            display: none;
            pointer-events: none;
        `;
        this.container.appendChild(tooltip);
        return tooltip;
    }
    
    hideTooltip() {
        const tooltip = document.getElementById('gantt-tooltip');
        if (tooltip) {
            tooltip.style.display = 'none';
        }
    }
    
    groupEventsByCategory(events) {
        return events.reduce((groups, event) => {
            const category = event.category || 'Other';
            if (!groups[category]) {
                groups[category] = [];
            }
            groups[category].push(event);
            return groups;
        }, {});
    }
    
    createElement(tag, styles) {
        const element = document.createElement(tag);
        Object.assign(element.style, styles);
        return element;
    }
    
    darkenColor(color, amount) {
        // Simple color darkening function
        const colorMap = {
            '#6f42c1': '#5a359a',
            '#28a745': '#1e7e34', 
            '#007bff': '#0056b3',
            '#ffc107': '#d39e00',
            '#20c997': '#17a2b8',
            '#dc3545': '#bd2130',
            '#17a2b8': '#117a8b'
        };
        return colorMap[color] || color;
    }
    
    showError(message) {
        this.chart.innerHTML = `
            <div style="display: flex; align-items: center; justify-content: center; height: 100%; color: #6c757d;">
                <div style="text-align: center;">
                    <i class="fas fa-exclamation-triangle" style="font-size: 2em; margin-bottom: 10px;"></i>
                    <div>${message}</div>
                </div>
            </div>
        `;
    }
    
    refresh() {
        if (this.data && this.data.thesis) {
            this.loadData(this.data.thesis.id);
        }
    }
}

// Export for use in templates
window.ThesisGanttChart = ThesisGanttChart;