#!/bin/bash
echo "=== AKS AI Platform Verification ==="
echo ""

# Check cluster
echo "✓ Checking cluster status..."
kubectl cluster-info

# Check KAITO
echo -e "\n✓ Checking KAITO installation..."
kubectl get pods -n kube-system | grep kaito

# Check namespaces
echo -e "\n✓ Checking namespaces..."
kubectl get namespaces | grep -E "(platform-system|data-science|model-serving|app-development)"

# Check node pools
echo -e "\n✓ Checking node pools..."
kubectl get nodes --show-labels | grep -E "(workload=gpu|agentpool)"

echo -e "\n✅ Setup verification complete!"
