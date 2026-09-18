(() => {
    const canvas = document.getElementById("monthlySpendingChart");
    if (!canvas || !window.monthlySpendingData || typeof Chart === "undefined") return;
    const styles = getComputedStyle(document.documentElement);
    const color = (name) => styles.getPropertyValue(name).trim();
    const reducedMotion = matchMedia("(prefers-reduced-motion: reduce)");
    const render = () => new Chart(canvas, {
        type: "bar",
        data: {
            labels: window.monthlySpendingData.labels,
            datasets: [{
                data: window.monthlySpendingData.totals,
                backgroundColor: color("--brown-medium"),
                maxBarThickness: 56
            }]
        },
        plugins: [{
            id: "visibleAmounts",
            afterDatasetsDraw(chart) {
                const {
                    ctx
                } = chart;
                ctx.save();
                ctx.fillStyle = color("--text-muted");
                ctx.font = `14px ${styles.getPropertyValue("--font-ui")}`;
                ctx.textAlign = "center";
                chart.getDatasetMeta(0).data.forEach((bar, index, bars) => {
                    // Avoid overlapping labels on long histories; exact values remain in the data table.
                    if (chart.chartArea.width / bars.length < 44) return;
                    const value = Number(chart.data.datasets[0].data[index]);
                    const label = new Intl.NumberFormat(document.documentElement.lang, {
                        notation: "compact",
                        maximumFractionDigits: 1
                    }).format(value);
                    ctx.fillText(label, bar.x, bar.y - 8);
                });
                ctx.restore();
            }
        }],
        options: {
            responsive: true,
            maintainAspectRatio: false,
            animation: reducedMotion.matches ? false : {
                duration: 200
            },
            layout: {
                padding: {
                    top: 32,
                    left: 12,
                    right: 12
                }
            },
            plugins: {
                legend: {
                    display: false
                },
                tooltip: {
                    callbacks: {
                        label: (context) => `${context.parsed.y.toFixed(2)} ﷼`
                    }
                }
            },
            scales: {
                x: {
                    grid: {
                        display: false
                    },
                    border: {
                        display: false
                    },
                    ticks: {
                        color: color("--text"),
                        maxRotation: 0,
                        autoSkip: true
                    }
                },
                y: {
                    beginAtZero: true,
                    display: false
                }
            }
        }
    });
    document.fonts.ready.then(render);
})();
