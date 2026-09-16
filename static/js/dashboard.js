const ctx = document.getElementById("spendingChart");

if (ctx && window.spendingData) {
    new Chart(ctx, {
        type: "doughnut",

        data: {
            labels: window.spendingData.labels,

            datasets: [{
                data: window.spendingData.totals,

                backgroundColor: [
                    "#7a5849",
                    "#a67c5b",
                    "#c9a66b",
                    "#e0c097",
                    "#8c6152",
                    "#b48a6d",
                    "#d9b48f",
                    "#6f4e3e"
                ],

                borderWidth: 0
            }]
        },

        options: {
            responsive: true,
            maintainAspectRatio: true,

            layout: {
                padding: {
                    top: 10,
                    right: 12,
                    bottom: 4,
                    left: 8
                }
            },

            plugins: {
                legend: {
                    display: false
                },

                tooltip: {
                    callbacks: {
                        label: function(context) {
                            return `${context.parsed.y.toFixed(2)} ﷼`;
                        }
                    }
                }
            },

            scales: {
                y: {
                    beginAtZero: true,

                    ticks: {
                        padding: 8,

                        callback: function(value) {
                            return value + " ﷼";
                        }
                    }
                }
            }
        }
    });
}

const monthlyCtx = document.getElementById("monthlySpendingChart");

if (monthlyCtx && window.monthlySpendingData) {
    new Chart(monthlyCtx, {
        type: "line",

        data: {
            labels: window.monthlySpendingData.labels,

            datasets: [{
                label: "Monthly Spending",
                data: window.monthlySpendingData.totals,

                borderColor: "#7a5849",
                backgroundColor: "rgba(122, 88, 73, 0.12)",

                borderWidth: 3,
                pointRadius: 4,
                pointHoverRadius: 6,

                tension: 0.35,
                fill: true
            }]
        },

        options: {
            responsive: true,

            plugins: {
                legend: {
                    display: false
                },

                tooltip: {
                    callbacks: {
                        label: function(context) {
                            return `${context.parsed.y.toFixed(2)} ﷼`;
                        }
                    }
                }
            },

            scales: {
                y: {
                    beginAtZero: true,

                    ticks: {
                        callback: function(value) {
                            return value + " ﷼";
                        }
                    }
                }
            }
        }
    });
}