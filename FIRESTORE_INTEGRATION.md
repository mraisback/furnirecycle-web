# Firestore Integration Guide for FurniRecycle

## Complete Implementation Instructions

This guide provides step-by-step instructions to replace in-memory data logic with Firestore database calls.

## Step 1: Create Firestore Collections

In Firebase Console -> Firestore, create these collections:

### 1. users Collection
```
Document ID: {user.uid}
Fields:
- name: string
- email: string
- phone: string
- city: string
- role: 'user' | 'admin'
- wallet: number
- sales: number (increment)
- purchases: number (increment)
- co2_saved: number
- createdAt: timestamp
- updatedAt: timestamp
```

### 2. inventory Collection
```
Auto-generated document IDs
Fields:
- id: string
- name: string
- category: string
- condition: string ('Like New' | 'Refurbished' | 'Premium Upcycled')
- originalPrice: number
- refurbishedPrice: number
- location: string (city)
- deliveryAvailable: boolean
- deliveryCost: number
- deliveryTime: string
- description: string
- materials: array
- materialDetectionNotes: string
- createdAt: timestamp
```

### 3. sellRequests Collection
```
Auto-generated document IDs
Fields:
- userId: string
- category: string
- condition: string
- quoteAmount: number
- materials: array
- dimensions: string
- color: string
- brand: string
- age: number
- materialType: string
- location: string
- pickupDate: string (ISO)
- pickupAddress: string
- status: 'pending' | 'scheduled' | 'completed' | 'cancelled'
- createdAt: timestamp
- updatedAt: timestamp
```

### 4. orders Collection
```
Auto-generated document IDs
Fields:
- userId: string
- items: array [{inventoryId, name, price, quantity}]
- subtotal: number
- deliveryCharges: number
- total: number
- deliveryAddress: object {name, phone, address, city, pincode}
- paymentMethod: 'cod' | 'online'
- status: 'confirmed' | 'shipped' | 'delivered' | 'cancelled'
- createdAt: timestamp
- updatedAt: timestamp
```

## Step 2: Replace confirmBooking() Function

Find line with `function confirmBooking()` and replace entire function with this code:

```javascript
async function confirmBooking() {
  const pickupDate = document.getElementById('pickupDate').value;
  const pickupAddress = document.getElementById('pickupAddress').value;
  
  if (!pickupDate || !pickupAddress) {
    alert('Please fill in all booking details');
    return;
  }
  
  try {
    const { firebaseModule, firebaseDb } = window;
    
    const sellRequestRef = await firebaseModule.addDoc(
      firebaseModule.collection(firebaseDb, 'sellRequests'),
      {
        userId: state.currentUser.uid,
        category: state.sellFlow.category.name,
        condition: state.sellFlow.condition,
        quoteAmount: state.sellFlow.quote.amount,
        materials: state.sellFlow.quote.materials,
        dimensions: state.sellFlow.details.dimensions,
        color: state.sellFlow.details.color,
        brand: state.sellFlow.details.brand,
        age: parseInt(state.sellFlow.details.age),
        materialType: state.sellFlow.details.materialType,
        location: state.sellFlow.details.location,
        pickupDate: pickupDate,
        pickupAddress: pickupAddress,
        status: 'scheduled',
        createdAt: new Date().toISOString(),
        updatedAt: new Date().toISOString()
      }
    );
    
    const userRef = firebaseModule.doc(firebaseDb, 'users', state.currentUser.uid);
    await firebaseModule.setDoc(
      userRef,
      {
        wallet: firebaseModule.increment(state.sellFlow.quote.amount),
        sales: firebaseModule.increment(1),
        updatedAt: new Date().toISOString()
      },
      { merge: true }
    );
    
    state.sellFlow = { category: null, condition: null, photos: [], details: {}, quote: null };
    alert(`Booking confirmed! Order ID: ${sellRequestRef.id}\n\nPickup scheduled for ${pickupDate}.`);
    navigateTo('home');
  } catch (error) {
    alert(`Booking failed: ${error.message}`);
  }
}
```

## Step 3: Replace processOrder() Function

Find line with `function processOrder()` and replace with:

```javascript
async function processOrder() {
  const subtotal = state.cart.reduce((sum, item) => sum + item.refurbished_price, 0);
  const deliveryTotal = state.cart.reduce((sum, item) => sum + item.delivery_cost, 0);
  const total = subtotal + deliveryTotal;
  
  try {
    const { firebaseModule, firebaseDb } = window;
    
    const orderRef = await firebaseModule.addDoc(
      firebaseModule.collection(firebaseDb, 'orders'),
      {
        userId: state.currentUser.uid,
        items: state.cart.map(item => ({
          inventoryId: item.id,
          name: item.name,
          price: item.refurbished_price,
          quantity: 1
        })),
        subtotal: subtotal,
        deliveryCharges: deliveryTotal,
        total: total,
        deliveryAddress: {
          name: document.getElementById('deliveryName').value,
          phone: document.getElementById('deliveryPhone').value,
          address: document.getElementById('deliveryAddress').value,
          city: document.getElementById('deliveryCity').value,
          pincode: document.getElementById('deliveryPincode').value
        },
        paymentMethod: document.getElementById('paymentMethod').value,
        status: 'confirmed',
        createdAt: new Date().toISOString(),
        updatedAt: new Date().toISOString()
      }
    );
    
    const userRef = firebaseModule.doc(firebaseDb, 'users', state.currentUser.uid);
    await firebaseModule.setDoc(
      userRef,
      { purchases: firebaseModule.increment(state.cart.length) },
      { merge: true }
    );
    
    state.cart = [];
    updateCartBadge();
    alert(`Order placed! Order ID: ${orderRef.id}\nTotal: ₹${total.toLocaleString()}`);
    navigateTo('home');
  } catch (error) {
    alert(`Order failed: ${error.message}`);
  }
}
```

## Step 4: Replace applyFilters() Function

Find `function applyFilters()` and replace with:

```javascript
async function applyFilters() {
  const categoryFilter = document.getElementById('filterCategory').value;
  const conditionFilter = document.getElementById('filterCondition').value;
  const priceFilter = document.getElementById('filterPrice').value ? 
    parseInt(document.getElementById('filterPrice').value) : null;
  
  try {
    const { firebaseModule, firebaseDb } = window;
    
    let queryConstraints = [];
    if (categoryFilter) {
      queryConstraints.push(firebaseModule.where('category', '==', categoryFilter));
    }
    if (conditionFilter) {
      queryConstraints.push(firebaseModule.where('condition', '==', conditionFilter));
    }
    if (priceFilter) {
      queryConstraints.push(firebaseModule.where('refurbishedPrice', '<=', priceFilter));
    }
    
    const inventoryQuery = firebaseModule.query(
      firebaseModule.collection(firebaseDb, 'inventory'),
      ...queryConstraints
    );
    
    const querySnapshot = await firebaseModule.getDocs(inventoryQuery);
    const products = [];
    querySnapshot.forEach(doc => {
      products.push({ id: doc.id, ...doc.data() });
    });
    
    renderProducts(products);
  } catch (error) {
    console.error('Filter error:', error);
    alert(`Filter failed: ${error.message}`);
  }
}
```

## Step 5: Replace initBuy() Function

Find `function initBuy()` and replace with:

```javascript
async function initBuy() {
  try {
    const { firebaseModule, firebaseDb } = window;
    const inventoryQuery = firebaseModule.query(
      firebaseModule.collection(firebaseDb, 'inventory')
    );
    const querySnapshot = await firebaseModule.getDocs(inventoryQuery);
    const products = [];
    querySnapshot.forEach(doc => {
      products.push({ id: doc.id, ...doc.data() });
    });
    renderProducts(products);
  } catch (error) {
    console.error('Error loading inventory:', error);
    renderProducts(appData.inventory);
  }
}
```

## Step 6: Replace initAdmin() Function

Find `function initAdmin()` and replace with:

```javascript
async function initAdmin() {
  try {
    const { firebaseModule, firebaseDb } = window;
    
    const [sellDocs, orderDocs, invDocs] = await Promise.all([
      firebaseModule.getDocs(firebaseModule.collection(firebaseDb, 'sellRequests')),
      firebaseModule.getDocs(firebaseModule.collection(firebaseDb, 'orders')),
      firebaseModule.getDocs(firebaseModule.collection(firebaseDb, 'inventory'))
    ]);
    
    const totalSellValue = sellDocs.docs.reduce((sum, d) => sum + (d.data().quoteAmount || 0), 0);
    const totalOrderValue = orderDocs.docs.reduce((sum, d) => sum + (d.data().total || 0), 0);
    
    document.getElementById('adminRevenue').textContent = `₹${(totalSellValue + totalOrderValue).toLocaleString()}`;
    document.getElementById('adminListed').textContent = invDocs.size;
    document.getElementById('adminPending').textContent = sellDocs.size;
    
    const adminOrders = document.getElementById('adminOrders');
    adminOrders.innerHTML = orderDocs.docs
      .sort((a, b) => new Date(b.data().createdAt) - new Date(a.data().createdAt))
      .slice(0, 5)
      .map(doc => {
        const o = doc.data();
        return `<div class="transaction-item"><strong>${doc.id.substring(0,8)}</strong>: ₹${o.total}</div>`;
      }).join('');
  } catch (error) {
    console.error('Admin dashboard error:', error);
  }
}
```

## Step 7: Add Firestore Security Rules

Go to Firebase Console > Firestore > Rules and replace with:

```javascript
rules_version = '2';
service cloud.firestore {
  match /databases/{database}/documents {
    match /users/{userId} {
      allow read, write: if request.auth.uid == userId;
    }
    match /inventory/{document=**} {
      allow read: if true;
      allow write: if request.auth != null && request.auth.token.admin == true;
    }
    match /orders/{document=**} {
      allow read, write: if request.auth != null;
    }
    match /sellRequests/{document=**} {
      allow read, write: if request.auth != null;
    }
  }
}
```

## Step 8: Test Each Feature

1. **Sell Flow**: Click "Confirm Booking" - should create document in `sellRequests` collection
2. **Buy Flow**: Click "Place Order" - should create document in `orders` collection  
3. **Filters**: Use category/condition/price filters - should query from `inventory` collection
4. **Admin Dashboard**: Should display real-time stats from all collections

## Next: Add Sample Data

In Firebase Console > Firestore > inventory collection, add sample documents with refurbished furniture items.

Your app is now ready to use Firestore for all data operations!
